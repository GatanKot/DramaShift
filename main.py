from RDramaAPIInterface import RDramaAPIInterface
import ScoredWrapper

scored_communities = ['consumeproduct', 'greatawakening', 'thedonald']


def get_scored_post_submission():
    # Fetch a community's posts between x hours ago and y hours ago
    filtered_posts = ScoredWrapper.fetch_posts_in_timeframe(community="consumeproduct", hour_start=1, hour_end=25)
    # sort posts by drama
    controversial_posts = ScoredWrapper.sort_posts_by_drama(filtered_posts)
    # take the top post and add a list of comments ranked by drama
    top_controversial_posts = controversial_posts[:1]  # for now, we only post the top post
    # TODO: set a drama filter threshold
    updated_posts_with_comments = ScoredWrapper.add_drama_ranked_comments_to_posts(top_controversial_posts)
    # format the final post for rdrama post submission
    single_submission = ScoredWrapper.get_rdrama_submit_format_for_one_post(updated_posts_with_comments[0])
    return single_submission


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
    if True:
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


if __name__ == "__main__":
    rdrama = get_rdrama_api()
    scored_submission = get_scored_post_submission()
    if True:
        print(scored_submission)
        input()
    post_rdrama_report(rdrama, scored_submission)
