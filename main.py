import argparse
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest as pytest

from DramaGraph import graph_drama
from RDramaAPIInterface import RDramaAPIInterface
import ScoredWrapper

scored_communities = ['consumeproduct', 'greatawakening', 'thedonald', 'kotakuinaction2']
TEST_MODE = True
POST_STORAGE_FILE = "stored_posts.npy"


def post_rdrama_report(rdrama_p: RDramaAPIInterface, post, test=TEST_MODE):
    if not post:
        return
    title = post["title"]
    url = post["link"]
    body = post["body"]
    if len(body) > 20000:
        body = body[0:19997] + "..."
    try:
        if not test:
            rdrama_p.make_post(title, url, body)
    except Exception as e:
        print(f"nice job retard: {e}")


def get_rdrama_api():
    website = "rdrama.net"
    with open("rdrama_auth_token", "r") as f:
        auth = f.read()
    https = True
    timeout = 10
    rdrama = RDramaAPIInterface(auth, website, timeout, https=https)
    return rdrama


def get_scored_drama_report(hour_end=26, top_n_posts=10, communities=['thedonald'],
                            catalogue=True, singlebest=True, dramagraph=False, threshold=0.0):
    filtered_posts = []
    for comm in communities:
        comm_filtered_posts = ScoredWrapper.fetch_posts_in_timeframe(community=comm,
                                                                     hour_end=hour_end)
        filtered_posts.extend(comm_filtered_posts)

    # sort posts by drama
    controversial_posts = ScoredWrapper.sort_posts_by_drama(filtered_posts)
    data = controversial_posts

    if dramagraph:
        graph_drama(
            [d['score_up'] / (d['score_up'] + d['score_down']) if (d['score_up'] + d['score_down']) > 0 else 0.5
             for d in data],  # Vote ratio
            [d['comments'] for d in data],  # Comment count
            [d['drama_score'] for d in data]  # Drama score
        )
    catalogue_submission = None
    single_submission = None

    if catalogue:
        top_controversial_posts = [p for p in controversial_posts if p['drama_score'] >= threshold]
        if not len(top_controversial_posts):
            print(f"No posts met controversial threshold >= {threshold} for catalogue")
        else:
            top_controversial_posts = top_controversial_posts[:top_n_posts]
            catalogue_submission = ScoredWrapper.get_rdrama_submit_format_for_catalogue(top_controversial_posts)

    if singlebest:
        best_controversial_post = controversial_posts[:1]
        best_drama_score = best_controversial_post[0]['drama_score']
        if best_drama_score < threshold:
            print(f"Best drama score {best_drama_score} was less than threshold {threshold} - no single submission.")
        else:
            best_post_with_comments = ScoredWrapper.add_drama_ranked_comments_to_posts(best_controversial_post)
            single_submission = ScoredWrapper.get_rdrama_submit_format_for_one_post(best_post_with_comments[0])

    return {'singlebest': single_submission, 'catalogue': catalogue_submission, 'posts': controversial_posts}


def recalc_fetch_t(posts, community, last_final_to_roll, safety_margin=0.25):
    # Filter to relevant community
    community_posts = posts[posts['community'].str.lower() == community].copy()

    # Need at least 2 posts to calculate rate
    if len(community_posts) < 20:
        return time.time() + 60 * 15  # fallback: 15 min from now

    # Sort by created time
    community_posts.sort_values(by='created', inplace=True)

    # Calculate time span in hours
    time_start = community_posts['created'].iloc[0] / 1000  # Convert ms to s
    time_end = community_posts['created'].iloc[-1] / 1000
    duration_hours = (time_end - time_start) / 3600.0

    if duration_hours == 0:
        return time.time() + 60 * 5  # fallback: 5 min

    # Posts per hour
    posts_per_hour = len(community_posts) / duration_hours

    # Estimate hours until `first_final_to_roll` new posts appear
    estimated_hours = last_final_to_roll / posts_per_hour

    # Apply safety margin and calculate fetch time
    wait_seconds = estimated_hours * 3600 * safety_margin
    next_fetch_time = community_posts['created'].iloc[-1] / 1000 + wait_seconds

    return next_fetch_time


def determine_finalizable(posts, finalizable_ind):
    # Get the 'created' time (epoch time) of the post
    created_time = posts.iloc[finalizable_ind]['created']

    # Get the current time (in ms since epoch)
    current_time = time.time() * 1000

    # Calculate the time difference between current time and 'created'
    time_diff = current_time - created_time

    # Multiply the time difference by 0.8
    adjusted_time_diff = time_diff * 0.8

    # Subtract the adjusted time difference from the current time
    finalizable_time = current_time - adjusted_time_diff

    return finalizable_time


def updatable_timer(t_wait):
    start_time = time.time()
    while time.time() - start_time < t_wait:
        elapsed_time = time.time() - start_time
        remaining_time = t_wait - elapsed_time

        # Calculate hours, minutes, and seconds from remaining time
        hours = int(remaining_time // 3600)
        minutes = int((remaining_time % 3600) // 60)
        seconds = int(remaining_time % 60)

        sys.stdout.write(f"\rTime remaining: {hours:02}:{minutes:02}:{seconds:02}")
        sys.stdout.flush()  # Ensure the output is updated immediately
        time.sleep(1)  # Update every second for smoothness

    # Final message after loop
    sys.stdout.write(f"\rTime remaining: 00:00:00\n")


def scored_monitor_loop(daily_post_hour=15, communities=scored_communities):
    comm_status = {'thedonald': {'strategy': 'roll', 'fetch_t': 0, 'roll_ind': 974},  # fixed for now.
                   'kotakuinaction2': {'strategy': 'fixed', 'fetch_t': 0},
                   'greatawakening': {'strategy': 'fixed', 'fetch_t': 0},
                   'consumeproduct': {'strategy': 'fixed', 'fetch_t': 0}}
    #  roll - use rolling estimate of drama, fixed - estimate at fixed time
    state = 'init'
    complete = False
    current_time = datetime.now(timezone.utc)
    time_post = datetime(current_time.year, current_time.month, current_time.day, daily_post_hour,
                         tzinfo=timezone.utc).timestamp()
    current_time = current_time.timestamp()
    if time_post - current_time < 0:
        time_post += 60 * 60 * 24
    all_posts = pd.DataFrame()
    # Load previous posts if available

    print(f"Next Posting Time: {datetime.fromtimestamp(time_post)}")
    time_fetch = 0
    while not complete:
        current_time = datetime.now(timezone.utc).timestamp()
        print(f"\nState: {state}\nCurrent Time: {datetime.fromtimestamp(current_time)}\n")
        if state == 'init':
            #  Read
            try:
                all_posts = pd.read_pickle(POST_STORAGE_FILE)
                for comm in comm_status:
                    if comm_status[comm]['strategy'] == 'roll':
                        comm_status[comm]['fetch_t'] = current_time + 20  # hardcode short for now
                time_fetch = min([comm['fetch_t'] if comm['strategy'] == 'roll' else 9999999999999999 for comm in
                                  comm_status.values()])
            except FileNotFoundError:
                print(f"File {POST_STORAGE_FILE} not found, repopulating all with fetch.")
                state = 'fetch'
                continue
            state = 'wait'
            continue

        elif state == 'wait':
            if time_fetch < time_post:
                t_wait = time_fetch - current_time
                if t_wait > 0:
                    print(f"Waiting to fetch...")
                    updatable_timer(t_wait)
                else:
                    print(f"Did not wait to fetch.")
                state = 'fetch'
            else:
                t_wait = time_post - current_time
                if t_wait > 0:
                    print(f"Waiting to post...")
                    updatable_timer(t_wait)
                else:
                    print(f"Did not wait to post.")
                state = 'post'
            continue

        elif state == 'fetch':
            for comm in communities:
                if comm_status[comm]['strategy'] == 'roll':
                    #  Index to set as maximum within pollable roll. Last accessible index thru scored api.
                    roll_ind = comm_status[comm]['roll_ind']
                    #  Earliest post in all_posts time
                    try:
                        epoch_t = all_posts[all_posts['community'].str.lower() == comm]['created'].max()
                    except KeyError:
                        epoch_t = time.time() * 1000 - 48 * 60 * 60 * 1000
                    #  Fetch until we reach the last post by created-date we've stored (first duplicate)
                    print(f"Fetch till {epoch_t}")
                    fetched_posts, ind = ScoredWrapper.fetch_posts_until_epoch_t(community=comm, epoch_t=epoch_t)
                    if ind:
                        print(f"Couldn't read past i={ind}")
                    #  Insert new posts at beginning.
                    fetched_posts = pd.DataFrame(fetched_posts)
                    all_posts = pd.concat([fetched_posts, all_posts], ignore_index=True)
                    #  Recalculate the threshold for accepting final drama score.
                    new_finalizable_t = determine_finalizable(all_posts[all_posts['community'].str.lower() == comm],
                                                              roll_ind)
                    #                   #  Recalculate final drama score starting at threshold.
                    uuid = all_posts[all_posts['created'] < new_finalizable_t].sort_values('created', ascending=False).iloc[0]['uuid']
                    print(f"Fetch from {uuid} all earlier than {new_finalizable_t} till finalized")
                    upd_scores, ind = ScoredWrapper.fetch_posts_finalize(uuid, posts=all_posts,
                                                                         community=comm)  # sort all_posts by created and start from new_finalizable_t
                    if ind:
                        print(f"Couldn't read past i={ind}")
                    upd_scores = pd.DataFrame(upd_scores)
                    #  Replace all_posts with same uuid as their updated entries in upd_scores.
                    all_posts.set_index('uuid', inplace=True)
                    upd_scores.set_index('uuid', inplace=True)

                    all_posts.update(upd_scores)

                    all_posts.reset_index(inplace=True)
                    upd_scores.reset_index(inplace=True)

                    finalized_posts = all_posts[all_posts['finalized'] == True]

                    # If there are any finalized posts, get the index of the first one based on 'created'
                    if not finalized_posts.empty:
                        first_finalized_index = finalized_posts[
                            'created'].idxmax()  # Get the index of the post with the earliest 'created'
                    else:
                        first_finalized_index = roll_ind

                    # Calculate last_finalized_to_roll as roll_ind - first_finalized_index
                    last_finalized_to_roll = roll_ind - first_finalized_index

                    comm_status[comm]['fetch_t'] = recalc_fetch_t(fetched_posts, comm,
                                                                  last_final_to_roll=last_finalized_to_roll)
            # Get minimum of fetch times
            time_fetch = min(
                [comm['fetch_t'] if comm['strategy'] == 'roll' else 9999999999999999 for comm in comm_status.values()])
            all_posts = ScoredWrapper.apply_drama_scores(all_posts)  # Just do for newly finalized todo
            all_posts.to_pickle(POST_STORAGE_FILE)
            print(all_posts[all_posts['finalized'] == True].sort_values('drama_score', ascending=False).iloc[0])
            print(all_posts[all_posts['finalized'] == False].sort_values('drama_score', ascending=False).iloc[0])
            state = 'wait'
            continue

        elif state == 'post':
            # Get finalized if 'roll' within timeframe of 'yesterday'.
            # #Alt, wait until all of yesterday is finalized.
            # Alt, just post latest finalized
            # Get from all other communities within timeframe
            # Combine posts and get submission texts.
            time_post = time_post + 24 * 60 * 60
            state = 'wait'
            continue


if __name__ == "__main__":

    pytest.main(["."])

    parser = argparse.ArgumentParser(description="Scored drama analysis & rdrama poster.")


    def to_lowercase(value):
        return value.lower()


    parser.add_argument("--mode", type=to_lowercase, required=True, default='default',
                        help="Operation mode ('monitor': Runs continuously for rolling window drama calculation,"
                             "posts catalogue and single best daily. Scored can only take last 1000 posts making this "
                             "necessary for time-normalized scores and longer timeframes. "
                             "'default': catalogue and single best, "
                             "'catalogue': top 10 or catalogue_max posts in 'drama report' style, "
                             "'singlebest': most controversial post within timeframe)")
    parser.add_argument("--timeframe", type=float, required=False,
                        help="Timeframe max in hours (24 = last 24 hours)")
    parser.add_argument("--communities", type=to_lowercase, nargs='+', required=True,
                        help="List of communities to track.")
    parser.add_argument("--catalogue_max", type=int, required=False,
                        help="Max entries to catalogue")
    parser.add_argument("--drama_filter", type=float, required=False,
                        help="Minimum drama score to post drama [0.0-1.0] every chud face is 0.2. "
                             "If all under, no posts.")
    parser.add_argument('--graph', action='store_true', help='Shows a graph of drama from posts.')

    args = parser.parse_args()
    timeframe = args.timeframe if args.timeframe else 24
    drama_filter = args.drama_filter if args.drama_filter else 0.0
    top_n_posts = args.catalogue_max if args.catalogue_max else 10
    singlebest = args.mode == 'default' or args.mode == 'singlebest'
    catalogue = args.mode == 'default' or args.mode == 'catalogue'
    dramagraph = args.graph
    communities = args.communities

    rdrama = get_rdrama_api()

    if args.mode == 'monitor':
        scored_monitor_loop(daily_post_hour=6)
    else:
        scored_submission = get_scored_drama_report(communities=communities,
                                                    hour_end=timeframe, singlebest=singlebest, catalogue=catalogue,
                                                    threshold=drama_filter, top_n_posts=top_n_posts,
                                                    dramagraph=dramagraph)
    input()
    if scored_submission['catalogue']:
        post_rdrama_report(rdrama, scored_submission['catalogue'])
    if scored_submission['singlebest']:
        post_rdrama_report(rdrama, scored_submission['singlebest'])
