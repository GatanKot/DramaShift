import argparse

from DramaGraph import graph_drama
from RDramaAPIInterface import RDramaAPIInterface
import ScoredWrapper

scored_communities = ['consumeproduct', 'greatawakening', 'thedonald', 'kotakuinaction2']


def get_scored_post_submission(community="thedonald", hour_start=0, hour_end=36, communities=[]):
    # Fetch a community's posts between x hours ago and y hours ago
    filtered_posts = ScoredWrapper.fetch_posts_in_timeframe(community=community, hour_start=hour_start,
                                                            hour_end=hour_end)
    # sort posts by drama
    controversial_posts = ScoredWrapper.sort_posts_by_drama(filtered_posts)
    data = controversial_posts
    graph_drama(
        [d['score_up'] / (d['score_up'] + d['score_down']) if (d['score_up'] + d['score_down']) > 0 else 0.5 for d in
         data],  # Vote ratio
        [d['comments'] for d in data],  # Comment count
        [d['drama_score'] for d in data]  # Drama score
    )
    # take the top post and add a list of comments ranked by drama
    top_controversial_posts = controversial_posts[:1]  # for now, we only post the top post
    # TODO: set a drama filter threshold
    updated_posts_with_comments = ScoredWrapper.add_drama_ranked_comments_to_posts(top_controversial_posts)
    # format the final post for rdrama post submission
    single_submission = ScoredWrapper.get_rdrama_submit_format_for_one_post(updated_posts_with_comments[0])
    return single_submission


def get_scored_drama_catalogue(community="thedonald", hour_start=0, hour_end=36, top_n_posts=10, communities=[]):
    if not communities:
        communities = [community]
    filtered_posts = []
    for comm in communities:
        comm_filtered_posts = ScoredWrapper.fetch_posts_in_timeframe(community=comm, hour_start=hour_start,
                                                                     hour_end=hour_end)
        filtered_posts.extend(comm_filtered_posts)

    # sort posts by drama
    controversial_posts = ScoredWrapper.sort_posts_by_drama(filtered_posts)
    data = controversial_posts
    graph_drama(
        [d['score_up'] / (d['score_up'] + d['score_down']) if (d['score_up'] + d['score_down']) > 0 else 0.5 for d in
         data],  # Vote ratio
        [d['comments'] for d in data],  # Comment count
        [d['drama_score'] for d in data]  # Drama score
    )
    top_controversial_posts = controversial_posts[:top_n_posts]
    catalogue_submission = ScoredWrapper.get_rdrama_submit_format_for_catalogue(top_controversial_posts)
    # TODO: set a drama filter threshold

    return catalogue_submission


def post_rdrama_report(rdrama_p: RDramaAPIInterface, post):
    title = post["title"]
    url = post["link"]
    body = post["body"]
    if len(body) > 20000:
        body = body[0:19997] + "..."
    try:
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


def get_drama_analysis(hour_start=0, hour_end=26, top_n_posts=10, communities=['thedonald'],
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
            [d['score_up'] / (d['score_up'] + d['score_down']) if (d['score_up'] + d['score_down']) > 0 else 0.5 for d in
             data],  # Vote ratio
            [d['comments'] for d in data],  # Comment count
            [d['drama_score'] for d in data]  # Drama score
        )
    catalogue_submission = None
    single_submission = None
    top_controversial_posts = controversial_posts[:top_n_posts]

    if catalogue:
        catalogue_submission = ScoredWrapper.get_rdrama_submit_format_for_catalogue(top_controversial_posts)

    if singlebest:
        best_controversial_posts = controversial_posts[:1]  # for now, we only post the top post
        updated_best_posts_with_comments = ScoredWrapper.add_drama_ranked_comments_to_posts(best_controversial_posts)
        single_submission = ScoredWrapper.get_rdrama_submit_format_for_one_post(updated_best_posts_with_comments[0])
    # TODO: set a drama filter threshold

    return {'singlebest': single_submission, 'catalogue': catalogue_submission, 'posts': controversial_posts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A script to process drama tracking.")

    def to_lowercase(value):
        return value.lower()

    parser.add_argument("--mode", type=to_lowercase, required=True, default='default',
                        help="Operation mode (e.g., 'monitor': Runs continuously for rolling window drama calculation,"
                             "posts catalogue and single best daily. Scored can only take last 1000 posts making this "
                             "necessary for time-normalized scores and longer timeframes. "
                             "'default': catalogue and single best, "
                             "'catalogue': top 10 or catalogue_max posts in 'drama report' style, "
                             "'singlebest': most controversial post within timeframe)")
    parser.add_argument("--timeframe", type=float, nargs=2, required=False,
                        help="Timeframe in hours (start and end)")
    parser.add_argument("--communities", type=to_lowercase, nargs='+', required=True,
                        help="List of communities to track")
    parser.add_argument("--catalogue_max", type=int, nargs=1, required=False,
                        help="Max entries to catalogue")
    parser.add_argument("--drama_filter", type=float, nargs=1, required=False,
                        help="Minimum drama score to post in catalogue or daily. If all under, no posts.")

    args = parser.parse_args()
    rdrama = get_rdrama_api()

    if args.mode == 'monitor':
        print("Monitor")
    elif args.mode == 'default':
        print("Catalogue & Most Dramatic Post")

    elif args.mode == 'catalogue':
        print("Catalogue")
    elif args.mode == 'singlebest':
        print("Most Dramatic Post")
        scored_submission = get_drama_analysis(communities=args.communities, hour_start=0, hour_end=35)
        post_rdrama_report(rdrama, scored_submission)

    #  main(args.mode, args.timeframe, args.communities)

    #
    scored_submission = get_scored_drama_catalogue(communities=scored_communities, hour_start=0, hour_end=24,
                                                   top_n_posts=10)
    # scored_submission = get_scored_drama_catalogue(communities=['thedonald'], hour_start=1, hour_end=24,
    #                                                top_n_posts=10)
    # single, catalogue = do_daily_drama_posts(communities=['consumeproduct','greatawakening'],hour_start=0,hour_end=999999)  # for getting past 1000

    print(scored_submission)
    input()
    post_rdrama_report(rdrama, scored_submission)
    # post_rdrama_report(rdrama, catalogue)
