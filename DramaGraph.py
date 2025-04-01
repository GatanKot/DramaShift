import matplotlib.pyplot as plt


def graph_drama(vote_ratio, comment, dramascore):
    plt.ion()
    plt.figure(figsize=(8, 6))
    scatter = plt.scatter(vote_ratio, comment, c=dramascore, cmap='viridis', alpha=0.75)
    plt.colorbar(scatter, label="Drama Score")
    plt.xlabel("Vote Ratio")
    plt.ylabel("Comment Count")
    plt.title("Drama Score Visualization")

    # Ensure all points are within visible bounds
    plt.xlim(-0.2, 1.2)  # Vote ratio should be between 0 and 1
    plt.ylim(0, max(comment) * 1.1 if comment else 1)  # Scale comments with some padding
    plt.draw()
    plt.pause(0.1)
    plt.show()
