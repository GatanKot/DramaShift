import argparse

import pytest as pytest

from DramaGraph import graph_drama
from RDramaAPIInterface import RDramaAPIInterface
import ScoredWrapper

scored_communities = ['consumeproduct', 'greatawakening', 'thedonald', 'kotakuinaction2']
TEST_MODE = True


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
        best_drama_score = best_controversial_post['drama_threshold']
        if best_drama_score < threshold:
            print(f"Best drama score {best_drama_score} was less than threshold {threshold} - no single submission.")
        else:
            best_post_with_comments = ScoredWrapper.add_drama_ranked_comments_to_posts(best_controversial_post)
            single_submission = ScoredWrapper.get_rdrama_submit_format_for_one_post(best_post_with_comments[0])

    return {'singlebest': single_submission, 'catalogue': catalogue_submission, 'posts': controversial_posts}


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
        print("Monitor")

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
