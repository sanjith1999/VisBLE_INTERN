import matplotlib.pyplot as plt
import cv2 as cv


def visualize_points_and_circle(points_list=[], circles_list=[], legends=[], symbol=[], fig_size=(10, 10), grid=False, title=[], x_lim=[], y_lim=[]):
    """ Visualizing List of Points and Circles
    :param points_list: list of points
    :param circles_list: list of circles [circle,edge_color(optional),threshold(optional))]
    :param legends: List of legends[points legends, circle legends]
    :param symbol: list of symbols
    :param fig_size: size of the output image ((10,10) by default)
    :param grid: Whether to use grids
    :param title: Setting Title to the plot
    :param x_lim: specifying x_lim (optional)
    :param y_lim: Specifying y_lim (optional)
    :return: void
    """

    # Setting Parameters
    legend_available = True
    if not symbol:
        symbol = ['.' for i in range(len(points_list))]
    if not legends:
        legend_available = False
        legends = [['' for i in range(len(points_list))], ['' for i in range(len(circles_list))]]

    plt.figure(figsize=fig_size)
    ax = plt.gca()
    ax.set_aspect('equal')
    for i, points in enumerate(points_list):
        plt.plot(points[:, 0], points[:, 1], symbol[i], label=legends[0][i])

    for i, circle in enumerate(circles_list):
        circ = circle[0]

        # Looking for edge_color
        if len(circle) > 1 and len(circle[1]):
            edge_color = circle[1]
        else:
            edge_color = 'green'

        draw_circle = plt.Circle((circ.X, circ.Y), circ.R, fill=False, edgecolor=edge_color, linewidth=2, label=legends[1][i])
        ax.add_artist(draw_circle)

        # Looking for threshold values
        if len(circle) > 2 and circle[2] < circ.R:
            threshold = circle[2]
            draw_inner = plt.Circle((circ.X, circ.Y), circ.R - threshold, fill=False, edgecolor=edge_color, linewidth=0.2, linestyle='--')
            draw_outer = plt.Circle((circ.X, circ.Y), circ.R + threshold, fill=False, edgecolor=edge_color, linewidth=0.2, linestyle='--')
            ax.add_artist(draw_inner)
            ax.add_artist(draw_outer)

    # verbose
    if legend_available:
        plt.legend()
    if grid:
        plt.grid()
    if title:
        plt.title(title)
    if x_lim:
        plt.xlim(x_lim)
    if y_lim:
        plt.ylim(y_lim)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    plt.tight_layout()

    plt.show()


def show_images(images, n_rows=1, size=5):
    """
    Showing Images using Matplotlib
    -----------------------------------
    images : list of images  with format [[image, color_specification(optional), title(optional)]]
    color_specification : 'g' -> normal gray image , 'c' -> normal color image , (color_conversion) -> for color images , (v_min, v_max) -> gray images
    n_rows : n_rows in the figure
    """

    # parameters
    n_images = len(images)
    n_cols = int(n_images / n_rows)
    fig_size = (n_cols * size, n_rows * 5)

    fig, ax = plt.subplots(n_rows, n_cols, figsize=fig_size)

    for i in range(n_images):
        # default image parameters
        color_im = True
        conversion = cv.COLOR_BGR2RGB
        v_min = 0
        v_max = 255

        # Specific Image Parameters
        if len(images[i]) > 1:
            if images[i][1] == 'g':
                color_im = False
            elif len(images[i][1]) == 2:
                color_im = False
                v_max = images[i][1][1]
                v_min = images[i][1][0]
            elif images[i][1] != 'c':
                conversion = images[i][1][0]
        title = len(images[i]) > 2

        # Displaying One Image
        if n_cols == 1 and n_rows == 1:
            if color_im:
                ax.imshow(cv.cvtColor(images[i][0], conversion))
            else:
                ax.imshow(images[i][0], cmap='gray', vmin=v_min, vmax=v_max)
            ax.set_xticks([])
            ax.set_yticks([])
            if title:
                ax.set_title(images[i][2], color='blue', fontsize=14)

        # Displaying Multiple Image in Same Row
        elif n_rows == 1:
            if color_im:
                ax[i].imshow(cv.cvtColor(images[i][0], conversion))
            else:
                ax[i].imshow(images[i][0], cmap='gray', vmin=v_min, vmax=v_max)
            ax[i].set_xticks([])
            ax[i].set_yticks([])
            if title:
                ax[i].set_title(images[i][2], color='blue', fontsize=14)

        # Displaying Images in Multiple Row
        else:
            if color_im:
                ax[i // n_cols][i % n_cols].imshow(cv.cvtColor(images[i][0], conversion))
            else:
                ax[i // n_cols][i % n_cols].imshow(images[i][0], cmap='gray', vmin=v_min, vmax=v_max)
            ax[i // n_cols][i % n_cols].set_xticks([])
            ax[i // n_cols][i % n_cols].set_yticks([])
            if title:
                ax[i // n_cols][i % n_cols].set_title(images[i][2], color='blue', fontsize=14)

    plt.show()
    return
