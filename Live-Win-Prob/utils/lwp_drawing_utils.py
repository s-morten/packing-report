import matplotlib.pyplot as plt
from matplotlib.patches import Arc
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import numpy as np


def draw_field(ax, mat, color="black"):
    """
    Draws a football pitch and a heatmap matrix

            Parameters:
                    ax (axis): Matplotlib axis object to plot on
                    mat ([[]]): Matrix of colormap of field
                    color (string): Color of field lines

            Returns:
                    Matplotlib Axis
    """
    ax.matshow(mat, extent=[0, 24, 0, 16], interpolation="nearest")

    # sizes
    STATSBOMB_WIDTH = 24
    STATSBOMB_HEIGHT = 16
    STANDARD_PITCH_SIZE_WIDTH = 120
    STANDARD_PITCH_SIZE_WIDTH = 80

    # outline and middle line
    ax.plot([0, 0], [0, STATSBOMB_HEIGHT], color=color)
    ax.plot([0, STATSBOMB_WIDTH], [STATSBOMB_HEIGHT, STATSBOMB_HEIGHT], color=color)
    ax.plot([STATSBOMB_WIDTH, STATSBOMB_WIDTH], [STATSBOMB_HEIGHT, 0], color=color)
    ax.plot([STATSBOMB_WIDTH, 0], [0, 0], color=color)
    ax.plot(
        [STATSBOMB_WIDTH / 2, STATSBOMB_WIDTH / 2], [0, STATSBOMB_HEIGHT], color=color
    )

    # middle circle
    centreCircle = plt.Circle(
        (STATSBOMB_WIDTH / 2, STATSBOMB_HEIGHT / 2), 1.85, color=color, fill=False
    )
    centreSpot = plt.Circle(
        (STATSBOMB_WIDTH / 2, STATSBOMB_HEIGHT / 2), 0.1, color=color
    )

    ax.add_patch(centreCircle)
    ax.add_patch(centreSpot)

    # left penalty area
    ax.plot([3.3, 3.3], [12, 4], color=color)
    ax.plot([0, 3.3], [12, 12], color=color)
    ax.plot([3.3, 0], [4, 4], color=color)

    # Create Arc and add it to our plot
    leftArc = Arc(
        (2.2, STATSBOMB_HEIGHT / 2),
        height=3.66,
        width=3.66,
        angle=0,
        theta1=310,
        theta2=50,
        color=color,
    )
    leftPenSpot = plt.Circle((2.2, STATSBOMB_HEIGHT / 2), 0.1, color=color)

    ax.add_patch(leftArc)
    ax.add_patch(leftPenSpot)

    # left 6 yard box
    ax.plot([1.1, 1.1], [9.8, 6.2], color=color)
    ax.plot([0, 1.1], [9.8, 9.8], color=color)
    ax.plot([1.1, 0], [6.2, 6.2], color=color)

    # right penalty box
    ax.plot([24 - 3.3, 24 - 3.3], [16 - 12, 16 - 4], color=color)
    ax.plot([24 - 0, 24 - 3.3], [16 - 12, 16 - 12], color=color)
    ax.plot([24 - 3.3, 24 - 0], [16 - 4, 16 - 4], color=color)

    # left 6 yard box
    ax.plot([24 - 1.1, 24 - 1.1], [16 - 9.8, 16 - 6.2], color=color)
    ax.plot([24 - 0, 24 - 1.1], [16 - 9.8, 16 - 9.8], color=color)
    ax.plot([24 - 1.1, 24 - 0], [16 - 6.2, 16 - 6.2], color=color)

    # right spots
    leftArc = Arc(
        (24 - 2.2, STATSBOMB_HEIGHT / 2),
        height=3.66,
        width=3.66,
        angle=0,
        theta1=130,
        theta2=230,
        color=color,
    )
    leftPenSpot = plt.Circle((24 - 2.2, STATSBOMB_HEIGHT / 2), 0.1, color=color)

    ax.add_patch(leftArc)
    ax.add_patch(leftPenSpot)

    return ax


def draw_xT_xG_plot(all_goals_slots, xT_home_slots, xT_away_slots):
    """draw a xG oder xT pyramide plot.

    Args:
        all_goals_slots (list): goals per slot
        xT_home_slots (list): list of xT/xG values per frame for the home team
        xT_away_slots (list): list of xT/xG values per frame for the away team

    Returns:
        fig, ax: fig and axes of the created plot
    """
    im = plt.imread("/home/morten/Develop/Live-Win-Prob/media/soccer-ball_26bd.png")
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(15, 10))

    for team_idx, x in enumerate(all_goals_slots):
        for idx, slot in enumerate(x):
            for goals in slot:
                xy = [idx + 0.4, -0.075]
                imageBox = OffsetImage(im, zoom=0.3)
                ab = AnnotationBbox(imageBox, xy, frameon=False)
                if team_idx == 0:
                    axes[0].add_artist(ab)
                else:
                    axes[1].add_artist(ab)

    tmp1 = np.max(xT_home_slots)
    tmp2 = np.max(xT_away_slots)
    maxval = np.max([tmp1, tmp2])
    maxval = round(maxval + 0.05, 1)
    tmp1 = np.min(xT_home_slots)
    tmp2 = np.min(xT_away_slots)
    minval = np.min([tmp1, tmp2])
    minval = round(minval - 0.05, 1)
    y = range(20)
    ticks = [0, 10, 20]
    label = ["Kick-Off", "HT", "FT"]

    axes[0].bar(y, xT_home_slots, align="edge", color="blue")
    axes[0].tick_params(axis="x", reset=True)
    axes[0].set_ylim([minval, maxval])
    axes[0].grid()
    axes[1].bar(y, xT_away_slots, align="edge", color="turquoise")
    axes[1].xaxis.tick_top()
    axes[1].set_ylim([minval, maxval])
    axes[1].grid()
    axes[1].invert_yaxis()

    axes[0].set_xticks(ticks=ticks, labels=label)
    axes[1].set_xticklabels(labels=label, visible=False)
    return fig, axes
