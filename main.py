from DramaGraph import graph_drama
from RDramaAPIInterface import RDramaAPIInterface
import ScoredWrapper

scored_communities = ['consumeproduct', 'greatawakening', 'thedonald']


def get_scored_post_submission(community="thedonald", hour_start=1, hour_end=31):
    # Fetch a community's posts between x hours ago and y hours ago
    filtered_posts = ScoredWrapper.fetch_posts_in_timeframe(community=community, hour_start=hour_start,
                                                            hour_end=hour_end)
    # sort posts by drama
    controversial_posts = ScoredWrapper.sort_posts_by_drama(filtered_posts)
    # take the top post and add a list of comments ranked by drama
    top_controversial_posts = controversial_posts[:1]  # for now, we only post the top post
    # TODO: set a drama filter threshold
    updated_posts_with_comments = ScoredWrapper.add_drama_ranked_comments_to_posts(top_controversial_posts)
    # format the final post for rdrama post submission
    single_submission = ScoredWrapper.get_rdrama_submit_format_for_one_post(updated_posts_with_comments[0])
    return single_submission


def get_scored_drama_catalogue(community="thedonald", hour_start=1, hour_end=31, top_n_posts=10, communities=[]):
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
    TEST_AUTH_TOKEN = ""
    if False:
        website = "localhost"
        auth = TEST_AUTH_TOKEN
        https = False
        timeout = 1
    else:
        website = "rdrama.net"
        with open("rdrama_auth_token", "r") as f:
            auth = f.read()
        https = True
        timeout = 10
    rdrama = RDramaAPIInterface(auth, website, timeout, https=https)
    return rdrama


def do_daily_drama_posts(community="thedonald", hour_start=2, hour_end=26, top_n_posts=10, communities=[]):
    if not communities:
        communities = [community]
    filtered_posts = []
    for comm in communities:
        comm_filtered_posts = ScoredWrapper.fetch_posts_in_timeframe(community=comm, hour_start=hour_start,
                                                                     hour_end=hour_end)
        filtered_posts.extend(comm_filtered_posts)

    # sort posts by drama
    controversial_posts = ScoredWrapper.sort_posts_by_drama(filtered_posts)
    top_controversial_posts = controversial_posts[:top_n_posts]
    catalogue_submission = ScoredWrapper.get_rdrama_submit_format_for_catalogue(top_controversial_posts)
    # TODO: set a drama filter threshold

    return catalogue_submission



if __name__ == "__main__":
    rdrama = get_rdrama_api()
    # scored_submission = get_scored_post_submission(community="consumeproduct", hour_start=1, hour_end=12)
    scored_submission = get_scored_drama_catalogue(communities=scored_communities, hour_start=0, hour_end=12,
                                                   top_n_posts=10)
    # scored_submission = get_scored_drama_catalogue(communities=['thedonald'], hour_start=1, hour_end=24,
    #                                                top_n_posts=10)
    print(scored_submission)
    exit()
    input()
    post_rdrama_report(rdrama, scored_submission)
