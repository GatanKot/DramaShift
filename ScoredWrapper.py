import requests
import time
import math
import re


## TODO: I am counting child nodes for reply count, but we should find all children of these nodes and use THAT as
## count, but direct children matter more. Algo.

## TODO improve controversy / engagement (drama) algo
## TODO: just grab post info don't do it multiple times. Monitor times which were pulled and store.
## TODO: This finds just controversial posts, but delusions themselves are drama-worthy, which are unanimous, and controversy may be in comments of big threads
## i.e. a thread of 10k comments likely has subthread more dramatic than niche post elsewhere


def slugify(title, max_length=32):
    # Replace apostrophes and other non-alphanumeric characters
    title = title.replace("’", "'")  # Replace special apostrophes
    # Remove all characters that are not alphanumeric or spaces
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())  # Keep hyphens in the slug

    # Replace spaces with hyphens
    slug = slug.replace(" ", "-")

    # Ensure the slug does not exceed the max length
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]  # Truncate and remove partial word

    return slug


# def get_posts(page_url):
#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
#                       "Chrome/58.0.3029.110 Safari/537.36"
#     }
#
#     response = requests.get(page_url, headers=headers)
#     if response.status_code == 200:
#         return response.text
#     else:
#         return None


def get_posts(from_id=None, sort='new', community=None):
    url = "https://scored.co/api/v2/post/" + sort + "v2.json"
    params = {
        'community': community,
        'from': from_id if from_id else '',
    }
    response = requests.get(url, params=params)
    return response.json() if response.status_code == 200 else None


def fetch_posts_in_timeframe(hour_end=25, hour_start=1, community="consumeproduct", relative_to_time=0):
    """
    get all posts from community that fall within time frame
    [current time - hour_start hours, current time - hour_end hours]

    :param relative_to_time: time in ms since last epoch that hour end and hour start are relative to
    :param hour_end: posts before hour_end hours before current_time will be ignored
    :param hour_start: posts after hour_start hours before current_time will be ignored
    :param community: name of scored.co/c/{community} e.g. consumeproduct, thedonald
    :return: list of post dicts
    """
    if not relative_to_time:
        relative_to_time = int(time.time() * 1000)  # current time

    all_posts = []
    from_id = None

    while True:
        data = get_posts(from_id, community=community, sort='new')  # gather page of posts from new starting at last
        if data and 'posts' in data:
            posts = data['posts']
            if len(all_posts):
                posts = posts[1:]  # remove duplicate entry (we fetch from last uuid inclusive)
            for post in posts:
                # Get post creation date (milliseconds)
                post_time = int(post['created'])
                post_hour_prev = ((relative_to_time - post_time) / (60 * 60 * 1000))
                # If the post is outside the time frame, stop fetching
                if post_hour_prev > hour_end:
                    return all_posts

                # Add post if within the time frame
                if post_hour_prev >= hour_start:
                    post["slug"] = slugify(post["title"])
                    post["link"] = f"https://scored.co/c/{community}/p/{post['uuid']}/{post['slug']}/c"
                    all_posts.append(post)

            # Get the ID of the last post to use for the next request
            if posts:
                from_id = posts[-1]['uuid']
            else:
                break  # No more posts
        else:
            break  # No data or error

    return all_posts


def calculate_drama_score(post, max_comments):
    # Vote Engagement, Vote Lean, Comment Engagement, Comment Lean, Topic Interest
    U = post.get('score_up', 0)
    D = post.get('score_down', 0)
    C = post.get('comments', 0)

    total_votes = U + D
    if total_votes == 0:
        return 0  # No votes, no controversy

    # Vote Controversy Score (VCS)
    VCS = (1 - abs(U - D) / (total_votes + 1)) * math.log(1 + total_votes)

    # Downvote-Based Controversy Boost (DBCB)
    DBCB = D / (total_votes + 1)

    # Engagement Score (E)
    if max_comments > 0:
        E = math.log(1 + C) / math.log(1 + max_comments)
    else:
        E = 0

    # Final Controversy Score
    FCS = (VCS * 0.5) + (DBCB * 0.3) + (E * 0.2)
    return FCS


def sort_posts_by_drama(posts):
    """

    :param posts:
    :return: List of posts sorted by drama score
    """
    if not posts:
        return []

    # Find max comments for normalization
    max_comments = max(post.get('comments', 0) for post in posts)

    # Compute scores and add as field
    for post in posts:
        post["drama_score"] = calculate_drama_score(post, max_comments)

    # Sort posts by score in descending order
    ranked_posts = sorted(posts, key=lambda p: p["drama_score"], reverse=True)

    return ranked_posts


def fetch_post_comments(id, uuid, slug):
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
            "permalink": f"https://scored.co/c/{comment.get('community', '')}/p/{uuid}/{slug}/c/{comment.get('uuid', '')}",
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
        uuid = post["uuid"]
        slug = post["slug"]
        comments = fetch_post_comments(id, uuid, slug)
        ranked_comments = rank_controversial_comments(comments)

        updated_posts.append({**post, "comments": ranked_comments})

    return updated_posts


def get_submission_title(post, title_truncate_len=497):
    title = "["
    if post["drama_score"] < 0.2:
        title += ":chudsmug: :2: :3: :4: :5:"
    elif post["drama_score"] < 0.4:
        title += ":doomer chud: " * 2 + " :3: :4: :5:"
    elif post["drama_score"] < 0.6:
        title += ":chudconcerned: " * 3 + " :4: :5:"
    elif post["drama_score"] < 0.8:
        title += ":chudseethe: " * 4 + ":5:"
    else:
        title += ":chudrage: " * 5
    title += "] "
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


def submission_comment_add(comment, text_truncate_len=280):
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


def get_rdrama_submit_format_for_one_post(post):
    """
    Returns a submission struct with a title, link, and text body strings.
    :param post: Post struct to be formatted for rdrama submit
    :return: Submission struct with title, body & link for submit via api
    """
    submission = {"title": "", "body": "", "link": ""}
    include_comments = min(5, len(post["comments"]))
    submission["title"] = get_submission_title(post)
    submission['link'] = post['link']
    submission["body"] = get_post_body_summary(post)
    submission['body'] += "#### Most Dramatic Comments \n\n"
    # TODO - don't include duplicate comments e.g. both parent and child separately, or multiple childs of same parent combine
    for i in range(0, include_comments):
        submission["body"] += submission_comment_add(post["comments"][i])
    submission["body"] += "---\n\n"
    submission[
        "body"] += ":marseysnappy: *'autodrama' for scored (thanks HeyMoon). Ping @GatanKot about bugs or " \
                   "ideas* :marseyagree:"
    return submission
