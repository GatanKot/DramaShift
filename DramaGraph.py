import matplotlib.pyplot as plt
import numpy as np

import ScoredWrapper


def graph_drama(vote_ratio, comment, dramascore, highlight_indices=True, mark_top=10,
                heatmap_function=ScoredWrapper.calculate_drama_score_vectorized_tup):
    plt.ion()
    fig, ax = plt.subplots(figsize=(8, 6))

    # Generate a grid of (x, y) values
    x_grid = np.linspace(0, 1.0, 100)  # Keep limits same as scatter plot
    y_grid = np.linspace(0, max(comment) * 1.1 if comment else 1, 100)
    X, Y = np.meshgrid(x_grid, y_grid)
    vect_func = np.vectorize(heatmap_function)
    Z = vect_func(X, Y)  # Compute f(x, y)

    # Plot the function f(x, y) = z as a heatmap
    contour = ax.contourf(X, Y, Z, levels=20, cmap='coolwarm', alpha=0.4)  # Background
    plt.colorbar(contour, label="Computed Drama Score")

    # Scatter plot of actual data
    scatter = ax.scatter(vote_ratio, comment, c=dramascore, cmap='cividis', edgecolors='black', alpha=0.85)
    plt.colorbar(scatter, label="Actual Drama Score")

    # Highlight specific points
    if highlight_indices:
        ax.scatter(
            np.array(vote_ratio)[:mark_top-1],
            np.array(comment)[:mark_top-1],
            s=100, edgecolors='red', facecolors='none', linewidth=2, label=f"Top {str(mark_top)}"
        )

    # Labels & limits
    ax.set_xlabel("Vote Ratio")
    ax.set_ylabel("Comment Count")
    ax.set_title("Drama Score Visualization")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, max(comment) * 1.1 if comment else 1)

    plt.legend()
    plt.draw()
    plt.pause(0.1)
    plt.show()

    # plt.savefig(filename, format='png')  # Change format to 'jpg', 'svg', etc. if needed
    # print(f"Graph saved as {filename}")
    # plt.close()
