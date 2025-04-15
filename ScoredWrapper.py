from datetime import datetime

import numpy as np
import requests
import time
from tqdm import tqdm
import math
import re

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

from SimplePostProgress import SimplePostProgress


## TODO: I am counting child nodes for reply count, but we should find all children of these nodes and use THAT as
## count, but direct children matter more. Algo.

## TODO: This finds just controversial posts, but delusions themselves are drama-worthy, which are unanimous, and controversy may be in comments of big threads
## i.e. a thread of 10k comments likely has subthread more dramatic than niche post elsewhere

## TODO Add unscored delete comparison unscored.arete.network/c/{community}/p/uuidofpost


def get_slugified_url(url, driver_path=r'C:\Program Files\WebDriver_proj\msedgedriver.exe'):
    # Set up Edge options
    options = Options()
    options.add_argument('--headless')  # Run in headless mode (optional)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # Initialize the Edge driver
    service = Service(driver_path)
    driver = webdriver.Edge(service=service, options=options)

    # Open the page
    driver.get(url)

    try:
        # Search for the first link that matches the specific pattern
        # Adjust the selector for a link with href in the format /c/{community}/p/{uuid}/{slug}/c
        link_element = driver.find_element(By.XPATH,
                                           "//a[contains(@href, '/c/') and contains(@href, '/p/') and contains(@href, '/c')]")

        # Extract the href attribute
        href = link_element.get_attribute('href')
        return href  # Return the link
    except Exception as e:
        print(f"Error: {e}")
        return None  # Return None if no link is found

    finally:
        # Close the driver
        driver.quit()


def get_posts(from_id=None, sort='new', community=None, rate_limit_s=1):
    url = "https://scored.co/api/v2/post/" + sort + "v2.json"
    params = {
        'community': community,
        'from': from_id if from_id else '',
    }
    response = requests.get(url, params=params)
    time.sleep(rate_limit_s)  # 600 / 10 minutes, or 1 / second
    return response.json() if response.status_code == 200 else None


def fetch_posts_until(callback, community="consumeproduct", from_id=None):
    print(f"Fetching posts from {community}.")
    all_posts = []
    from_id = from_id
    complete = False
    progress = SimplePostProgress()
    t = 0
    while not complete:
        data = get_posts(from_id, community=community, sort='new')
        if not data or 'posts' not in data:
            break
        posts = data['posts']
        if len(all_posts):
            posts = posts[1:]  # remove duplicate
        else:
            t = posts[0]['created']

        for post in posts:
            if t < post['created']:
                print(f"Looped to start {post}, {all_posts[-1]}\n{data}")
                complete = True
                break
            t = post['created']
            if not callback(post):
                complete = True
                break
            progress.update(len(all_posts))
            post["salted_link"] = f"https://scored.co/c/{community}/p/{post['uuid']}/c"
            post["link"] = ""
            post['finalized'] = False
            all_posts.append(post)
        if posts:
            from_id = posts[-1]['uuid']
        else:
            break

        if not data['has_more_entries']:
            progress.close()
            return all_posts, len(all_posts) - 1
    progress.close()
    return all_posts, None


# Wrapper that mimics original function signature
def fetch_posts_in_timeframe(hour_end=25, community="consumeproduct", relative_to_time=0):
    if not relative_to_time:
        relative_to_time = int(time.time() * 1000)

    def within_timeframe(post):
        post_time = int(post['created'])
        post_hour_prev = ((relative_to_time - post_time) / (60 * 60 * 1000))
        return hour_end >= post_hour_prev

    posts, stop_index = fetch_posts_until(within_timeframe, community=community)
    return posts, stop_index


# Another usage with UUID stopping condition
def fetch_posts_until_uuid(stop_uuid, community="consumeproduct"):
    def until_uuid(post):
        return post['uuid'] != stop_uuid

    posts, stop_index = fetch_posts_until(until_uuid, community=community)
    return posts, stop_index


# Another usage with UUID stopping condition
def fetch_posts_finalize(start_uuid, c_time, posts, community="consumeproduct"):
    def until_found_finalized(post):
        # Check if post['uuid'] exists in the posts DataFrame
        post_in_df = posts[posts['uuid'] == post['uuid']]
        if post['created'] > c_time:
            print(f"Bug where post {post} passed before expected time {c_time}.")
            return False
        if post_in_df.empty:
            return True  # If the post uuid is not found in the dataframe, return True

        # Check if 'finalized' exists in the row and return whether it's not True
        return post_in_df.iloc[0].get('finalized', False) != True

    posts, stop_index = fetch_posts_until(until_found_finalized, community=community, from_id=start_uuid)
    for new_post in posts:
        new_post['finalized'] = True
    return posts, stop_index


def fetch_posts_until_epoch_t(epoch_t, community="consumeproduct"):
    def until_t(post):
        return post['created'] > epoch_t

    posts, stop_index = fetch_posts_until(until_t, community=community)
    return posts, stop_index


def calculate_drama_score_vectorized(up, down, comm, in_ratio=None):
    """ Fully vectorized version of calculate_drama_score """

    # Compute the ratio
    if in_ratio is not None:
        ratio = np.asarray(in_ratio, dtype=np.float64)
    else:
        total_votes = up + down
        ratio = np.divide(up, total_votes, where=total_votes != 0, out=np.zeros_like(up, dtype=np.float64))

    # Sentiment Factor (vectorized piecewise function)
    sentiment_factor = np.where(
        ratio <= 0.5,
        np.where(
            ratio < 0.1825,
            np.minimum(1, 0.6 + 6 * (ratio ** 2)),
            np.minimum(1, 1 - 1.985 * ((ratio - 0.5) ** 2))
        ),
        np.where(
            ratio > 0.884,
            np.minimum(1, 6 * ((ratio - 1) ** 2)),
            np.minimum(1, 1 - 4.058 * ((ratio - 0.5) ** 2))
        )
    )

    # Engagement Factor (vectorized piecewise function)
    engagement_factor = np.where(
        comm < 28,
        (comm ** 3) / 100000,
        np.where(
            comm < 58,
            0.2 + (comm - 27.144) / 150,
            np.where(
                comm < 97,
                0.4 + ((comm - 57.144) ** 0.875) / 125,
                np.where(
                    comm < 170,
                    0.6 + ((comm - 96.739) ** 0.75) / 125,
                    0.8 + ((comm - 169.83) ** 0.4) / 125  # exceeds 1 at 3296
                )
            )
        )
    )

    # Compute drama score
    drama_score = sentiment_factor * engagement_factor
    return drama_score


def calculate_drama_score(up=0, down=0, comm=0, in_ratio=None):
    """
    Calculates the drama of a post using only up, down votes and comments. Time not controlled.
    Think of it as: up / down ratio estimates sentiment, sentiment_factor peaks at half 'agree' half 'disagree'
    Max comment engagement can only reach the limit of sentiment_factor. Piecewise function means you have diminishing
    returns after ~50 comments peaking at ~3000. Unit tests have examples but e.g.
    + 1  / - 1,  0 comments     = + 1000/ - 0, 3000 comments            = + 0 / - 100, 0 comments   ()      0.0
    + 50 / - 50, 28             = + 920 / - 80, 3000                    = + 0 / - 100, 47           (*)     0.2
    + 50 / - 50, 58             = + 880 / - 120, 3000                   = + 0 / - 100, 114          (**)    0.4
    + 50 / - 50, 97             = + 680 / - 320, 3000                   = + 0 / - 100, 3000         (***)   0.6
    + 500 / - 500, 170          = + 720 / - 280, 3000                   = + 180 / - 820, 3000       (****)  0.8
    + 500 / - 500, 3000         = + 500 / - 500, 3000                   = + 500 / - 500, 3000       (*****) 1.0

    :param in_ratio: workaround for DramaGraph
    :param up
    :param down
    :param comm
    :return: value between 0 and 1 higher is more dramatic
    """
    if in_ratio:
        ratio = in_ratio
    else:
        total_votes = up + down
        if total_votes == 0:
            return 0  # maybe a few comments but unlikely to have drama
        ratio = up / (up + down)

    #  piecewise from desmos

    if ratio <= 0.5:  # high negative sentiment is more dramatic
        if ratio < 0.1825:
            sentiment_factor = min(1, 0.6 + 6 * (ratio ** 2))
        else:
            sentiment_factor = min(1, 1 - 1.985 * ((ratio - 0.5) ** 2))
    else:
        if ratio > 0.93:
            sentiment_factor = min(1, 6 * ((ratio - 1) ** 2))
        else:
            sentiment_factor = min(1, 1 - 4.058 * ((ratio - 0.5) ** 2))
    if comm < 28:
        engagement_factor = (comm ** 3) / 100000
    elif comm < 58:
        engagement_factor = 0.2 + (comm - 27.144) / 150
    elif comm < 97:
        engagement_factor = 0.4 + ((comm - 57.144) ** 0.875) / 125
    elif comm < 170:
        engagement_factor = 0.6 + ((comm - 96.739) ** 0.75) / 125
    else:
        engagement_factor = 0.8 + ((comm - 169.83) ** 0.4) / 125  # exceeds 1 at 3296
    drama_score = sentiment_factor * engagement_factor
    return drama_score


def calculate_drama_score_vectorized_tup(x, y):
    """
    Vectorized function equivalent to calling calculate_drama_score with in_ratio=x and comm=y.
    """
    # Ensure that inputs are numpy arrays for element-wise operations
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    # We assume `calculate_drama_score_vectorized` is already vectorized,
    # so we can call it directly for each element-wise pair (x, y).
    return calculate_drama_score_vectorized(up=x * (x + 1),  # Just an example of how you would use x
                                            down=(1 - x) * (x + 1),  # Similarly handle downvotes
                                            comm=y)


def calculate_post_drama_score(post):
    return calculate_drama_score(post['score_up'], post['score_down'], post['comments'])


def apply_drama_scores(df):
    df['drama_score'] = df.apply(
        lambda row: calculate_drama_score(row['score_up'], row['score_down'], row['comments']),
        axis=1
    )
    return df


def sort_posts_by_drama(posts):
    """

    :param posts:
    :return: List of posts sorted by drama score
    """
    if not posts:
        return []

    # Compute scores and add as field
    for post in posts:
        post["drama_score"] = calculate_post_drama_score(post)

    # Sort posts by score in descending order
    ranked_posts = sorted(posts, key=lambda p: p["drama_score"], reverse=True)

    return ranked_posts


def fetch_post_comments(id):
    url = f"https://api.scored.co/api/v2/post/post.json?id={id}&comments=true&commentSort=controversial"
    response = requests.get(url)

    if response.status_code != 200:
        return None  # Handle failure case

    data = response.json()

    # Extract relevant fields
    post_info = {
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "score": data.get("score", 0),  # score_down score_up comments (num count)
        "comments": []
    }

    # Extract comments
    for comment in data.get("comments", []):
        post_info["comments"].append({
            "username": comment.get("author", "Unknown"),
            "score": comment.get("score", 0),
            "score_up": comment.get("score_up", 0),
            "score_down": comment.get("score_down", 0),
            "reply_count": len(comment.get("child_ids", [])),
            "id": comment.get("id", ""),
            "uuid": comment.get("uuid", ""),
            "comment_parent_id": comment.get("comment_parent_id", 0),
            "child_ids": comment.get("child_ids", []),
            "body": comment.get("content", ""),
            "date": comment.get("created", "")
        })
    # Replace parent and child ids with pointers to other comments
    comment_dict = {comment["id"]: comment for comment in post_info["comments"]}

    for comment in post_info["comments"]:
        parent_id = comment["comment_parent_id"]
        child_ids = comment["child_ids"]

        # Replace parent ID with actual reference if it exists
        comment["comment_parent"] = comment_dict.get(parent_id, None)

        # Replace child IDs with actual references
        comment["child_comments"] = [comment_dict[child_id] for child_id in child_ids if child_id in comment_dict]
    return post_info["comments"]


def rank_controversial_comments(comments):
    """

    :param comments: List of comment struct
    :return: List of comment struct sorted by comment drama score
    """
    if not comments:
        return []

    max_replies = max(c["reply_count"] for c in comments) if comments else 1

    def comment_score(comment):
        total_votes = comment["score_up"] + comment["score_down"]
        controversy = 1 - abs(
            (comment["score_up"] - comment["score_down"]) / (total_votes + 1)) if total_votes > 0 else 0
        engagement = math.log(1 + comment["reply_count"]) / math.log(1 + max_replies) if max_replies > 0 else 0
        return controversy * 0.5 + engagement * 0.5

    return sorted(comments, key=comment_score, reverse=True)


def add_drama_ranked_comments_to_posts(posts):
    """
    Fetches all comments from each post in posts, then sorts the comments by drama score

    :param posts: list of posts struct
    :return: list of posts struct with dramasort comments
    """
    updated_posts = []

    for post in posts:
        id = post["id"]
        comments = fetch_post_comments(id)
        ranked_comments = rank_controversial_comments(comments)

        updated_posts.append({**post, "comments": ranked_comments})

    return updated_posts


def numeric_score_to_string_descriptor(score):
    if score == 0:
        return "[ :chudcheers: ]"
    descriptor = "[ "
    if score < 0.2:
        descriptor += ":chudsmug: "
    elif score < 0.4:
        descriptor += ":doomerchud: " * 2
    elif score < 0.6:
        descriptor += ":chudconcerned: " * 3
    elif score < 0.8:
        descriptor += ":chudseethe: " * 4
    else:
        descriptor += ":chudrage: " * 5
    descriptor += "] "
    return descriptor


def get_singlepost_submission_title(post, title_truncate_len=497):
    title = numeric_score_to_string_descriptor(post["drama_score"])
    title += post["title"]
    return title[:title_truncate_len] + "..." if len(title) > title_truncate_len else title


def strip_html_tags(text):
    # Remove all HTML tags using regex
    return re.sub(r'<.*?>', '', text)


def strip_newlines(text):
    return text.replace("\n", " ")


def strip_text(text):
    text = strip_html_tags(text)
    text = strip_newlines(text)
    return text


def submission_comment_add(comment, text_truncate_len=400):
    text = ""
    comment_parent = comment["comment_parent"]
    if comment_parent:
        body = strip_text(comment_parent['body'])
        text += f"> {body[:text_truncate_len] + '...' if len(body) > text_truncate_len else body}"
        text += f" (+{comment_parent['score_up']}/-{comment_parent['score_down']})"
        text += "\n\n>"
    body = strip_text(comment['body'])
    text += f"> [{body[:text_truncate_len] + '...' if len(body) > text_truncate_len else body}"
    text += f"]({comment['permalink']})"
    text += f" (+{comment['score_up']}/-{comment['score_down']})"
    text += "\n\n<br>\n\n"
    return text


def get_post_body_summary(post, text_truncate_len=1000):
    text = ""
    if post['raw_content']:
        text = "> " + strip_text(post['raw_content'])
        text = text[:text_truncate_len] + "..." if len(text) > text_truncate_len else text
        text += "\n\n"
    return text


def get_finalized_post_urls(post):
    slug_url = get_slugified_url(post["salted_link"])
    post["link"] = slug_url
    linked_comments = post["comments"]
    for comment in linked_comments:
        comment["permalink"] = post['link'] + f"/{comment['uuid']}"
    post["comments"] = linked_comments  # idk about python copy stuff
    return post


def get_rdrama_submit_format_for_one_post(post):
    """
    Returns a submission struct with a title, link, and text body strings.
    :param post: Post struct to be formatted for rdrama submit
    :return: Submission struct with title, body & link for submit via api
    """
    submission = {"title": "", "body": "", "link": ""}
    include_comments = min(5, len(post["comments"]))
    submission["title"] = get_singlepost_submission_title(post)
    if not post["link"]:
        post = get_finalized_post_urls(post)
    submission['link'] = post['link'] + '?commentSort=controversial'
    submission["body"] = get_post_body_summary(post)
    submission['body'] += "#### Most Dramatic Comments \n\n"
    # TODO - don't include duplicate comments e.g. both parent and child separately, or multiple childs of same parent combine
    for i in range(0, include_comments):
        submission["body"] += submission_comment_add(post["comments"][i])
    submission["body"] += "---\n\n"
    submission[
        "body"] += ":marseysnappy: *Like HeyMoon's 'autodrama' but for scored. @ GatanKot about bugs or " \
                   "ideas* :marseyagree:"
    return submission


def get_catalogue_title():
    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y-%m-%d")
    title = f"Scored.co Drama Report :chudrage: {formatted_date}"
    return title


def get_tabulated_catalogue_posts(posts, title_char_max_len=88):
    html_str = "<table>\n"
    table_headers = ["Score", "Post", "Community", "Votes", "Comments"]
    html_str += "<tr>\n"
    for header in table_headers:
        html_str += f"<th>{header}</th>\n"
    html_str += "</tr>"
    for post in posts:
        html_str += "<tr>"
        html_str += f"<td>{numeric_score_to_string_descriptor(post['drama_score'])}</td>\n"
        html_str += f"<td><a href={post['salted_link']}>" \
                    f"{post['title'][:title_char_max_len] + '...' if len(post['title']) > title_char_max_len else post['title']}" \
                    f"</a></td>\n"
        html_str += f"<td>{post['community']}</td>\n"
        html_str += f"<td>(+{post['score_up']}/-{post['score_down']})</td>\n"
        html_str += f"<td>{post['comments']}</td>\n"
        html_str += "</tr>\n"
    html_str += "</table>\n"
    return html_str


def get_rdrama_submit_format_for_catalogue(posts):
    submission = {"title": get_catalogue_title(), "body": "#### Top Drama\n", "link": ""}
    submission["body"] += get_tabulated_catalogue_posts(posts)
    submission["body"] += ":marseysnappy: *Like HeyMoon's 'autodrama' but for scored. @ GatanKot about bugs or " \
                          "ideas* :marseyagree:"
    return submission
