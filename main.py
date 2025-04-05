import argparse
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


def get_scored_drama_report(hour_start=0, hour_end=26, top_n_posts=10, communities=['thedonald'],
                            catalogue=True, singlebest=True, dramagraph=False, threshold=0.0):
    filtered_posts = []
    for comm in communities:
        comm_filtered_posts = ScoredWrapper.fetch_posts_in_timeframe(community=comm, hour_start=hour_start,
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


def recalc_fetch_t(posts, community):
    return 0


def determine_finalizable(posts, finalizable_ind):
    return 0


def scored_monitor_loop(daily_post_hour=2, communities=scored_communities):
    comm_status = {'thedonald': {'strategy': 'roll', 'fetch_t': 0, 'roll_ind': 0},
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
        print(f"State: {state}\nCurrent Time: {datetime.fromtimestamp(current_time)}")
        if state == 'init':
            #  Read
            try:
                all_posts = pd.read_pickle(POST_STORAGE_FILE)
                for comm in comm_status:
                    if comm_status[comm]['strategy'] == 'roll':
                        comm_status[comm]['fetch_t'] = recalc_fetch_t(all_posts, comm)
                time_fetch = min(comm['fetch_t'] if comm['strategy'] == 'roll' else 999999999 for comm in comm_status.values())
            except FileNotFoundError:
                print(f"File {POST_STORAGE_FILE} not found, repopulating all with fetch.")
                all_posts = []
                state = 'fetch'
                continue
            state = 'wait'
            continue

        elif state == 'wait':
            if time_fetch < time_post:
                t_wait = time_fetch - current_time
                if t_wait > 0:
                    print(f"Waiting {int(int(t_wait) / 60)} minutes to fetch.")
                    time.sleep(time_fetch - current_time)
                else:
                    print(f"Did not wait to fetch.")
                state = 'fetch'
            else:
                t_wait = time_post - current_time
                if t_wait > 0:
                    print(f"Waiting {int(int(t_wait) / 60)} minutes to post.")
                    time.sleep(time_fetch - current_time)
                else:
                    print(f"Did not wait to post.")
                state = 'post'
            continue

        elif state == 'fetch':
            for comm in communities:
                if comm_status[comm]['strategy'] == 'roll':
                    roll_ind = comm_status[comm]['roll_ind']
                    epoch_t = all_posts[all_posts['community'] == comm]['created'].min()
                    #  Fetch until we get a repeat
                    fetched_posts = ScoredWrapper.fetch_posts_till_time(community=comm, t=epoch_t)
                    all_posts.append(fetched_posts)
                    new_finalizable_t = determine_finalizable(all_posts[all_posts['community'] == comm], roll_ind)
#                     # Update all posts from the minimum time of validity until we can no longer access
                    uuid = all_posts[all_posts['created'] >= new_finalizable_t].sort_values('created').iloc[0]['uuid']
                    ScoredWrapper.update_posts_dramascore_from(uuid)  # sort all_posts by created and start from new_finalizable_t
#                     # Recalculate when we should check again for this community
                    comm_status[comm]['fetch_t'] = recalc_fetch_t(all_posts, comm)
            # Get minimum of fetch times
            time_fetch = min(comm['fetch_t'] if comm['strategy'] == 'roll' else 999999999 for comm in comm_status.values())
            all_posts.to_pickle(POST_STORAGE_FILE)
            state = 'wait'
            continue

        elif state == 'post':
            # post_rdrama_report(wefojawef)  # Everything regardless fixed or roll, but > x hours ago
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
    parser.add_argument("--timeframe", type=float, nargs=2, required=False,
                        help="Timeframe in hours (start and end)")
    parser.add_argument("--communities", type=to_lowercase, nargs='+', required=True,
                        help="List of communities to track.")
    parser.add_argument("--catalogue_max", type=int, nargs=1, required=False,
                        help="Max entries to catalogue")
    parser.add_argument("--drama_filter", type=float, nargs=1, required=False,
                        help="Minimum drama score to post drama [0.0-1.0] every chud face is 0.2. "
                             "If all under, no posts.")
    parser.add_argument('--graph', action='store_true', help='Shows a graph of drama from posts.')

    args = parser.parse_args()
    timeframe = args.timeframe if args.timeframe else [0, 24]
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
        scored_submission = get_scored_drama_report(communities=communities, hour_start=timeframe[0],
                                                    hour_end=timeframe[1], singlebest=singlebest, catalogue=catalogue,
                                                    threshold=drama_filter, top_n_posts=top_n_posts,
                                                    dramagraph=dramagraph)
    input()
    if scored_submission['catalogue']:
        post_rdrama_report(rdrama, scored_submission['catalogue'])
    if scored_submission['singlebest']:
        post_rdrama_report(rdrama, scored_submission['singlebest'])
