# Dependencies
import cv2 as cv
import matplotlib.pyplot as plt


def show_images(images, n_rows=1, size=5, show_ticks=False):
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
    fig_size = (n_cols * size, n_rows * size)
    

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
            if not show_ticks:
                ax.set_xticks([])
                ax.set_yticks([])
            else:
                ax.axis('off')
            if title:
                ax.set_title(images[i][2], color='blue', fontsize=14)

        # Displaying Multiple Image in Same Row
        elif n_rows == 1:
            if color_im:
                ax[i].imshow(cv.cvtColor(images[i][0], conversion))
            else:
                ax[i].imshow(images[i][0], cmap='gray', vmin=v_min, vmax=v_max)
            if not show_ticks:
                ax[i].set_xticks([])
                ax[i].set_yticks([])
            else:
                ax[i].axis('off')
            if title:
                ax[i].set_title(images[i][2], color='blue', fontsize=14)

        # Displaying Images in Multiple Row
        else:
            if color_im:
                ax[i // n_cols][i %
                                n_cols].imshow(cv.cvtColor(images[i][0], conversion))
            else:
                ax[i // n_cols][i %
                                n_cols].imshow(images[i][0], cmap='gray', vmin=v_min, vmax=v_max)
            if not show_ticks:
                ax[i // n_cols][i % n_cols].set_xticks([])
                ax[i // n_cols][i % n_cols].set_yticks([])
            else:
                ax[i // n_cols][i % n_cols].axis('off')
            if title:
                ax[i // n_cols][i %
                                n_cols].set_title(images[i][2], color='blue', fontsize=14)

    plt.show()
    return


