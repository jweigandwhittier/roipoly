import sys
import logging
import warnings

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.widgets import Button

logger = logging.getLogger(__name__)

warnings.simplefilter('always', DeprecationWarning)


def deprecation(message):
    warnings.warn(message, DeprecationWarning)


class RoiPoly:

    def __init__(self, fig=None, ax=None, color='b',
                 roicolor=None, show_fig=True, close_fig=True):
        """

        Parameters
        ----------
        fig: matplotlib figure
            Figure on which to create the ROI
        ax: matplotlib axes
            Axes on which to draw the ROI
        color: str
           Color of the ROI
        roicolor: str
            deprecated, use `color` instead
        show_fig: bool
            Display the figure upon initializing a RoiPoly object
        close_fig: bool
            Close the figure after finishing ROI drawing
        """

        if roicolor is not None:
            deprecation("Use 'color' instead of 'roicolor'!")
            color = roicolor

        if fig is None:
            fig = plt.gcf()
        if ax is None:
            ax = plt.gca()

        self.start_point = []
        self.end_point = []
        self.previous_point = []
        self.x = []
        self.y = []
        self.line = None
        self.completed = False  # Has ROI drawing completed?
        self.color = color
        self.fig = fig
        self.ax = ax
        self.close_figure = close_fig

        # Mouse event callbacks
        self.__cid1 = self.fig.canvas.mpl_connect(
            'motion_notify_event', self.__motion_notify_callback)
        self.__cid2 = self.fig.canvas.mpl_connect(
            'button_press_event', self.__button_press_callback)

        if show_fig:
            self.show_figure()

    @staticmethod
    def show_figure():
        if sys.flags.interactive:
            plt.show(block=False)
        else:
            plt.show(block=True)

    def get_mask(self, image):
        """Get binary mask of the ROI polygon.

        Parameters
        ----------
        image: numpy array (2D)
            Image that the mask should be based on. Only used for determining
            the shape of the binary mask (which is made equal to the shape of
            the image)

        Returns
        -------
        numpy array (2D)

        """
        ny, nx = np.shape(image)
        poly_verts = ([(self.x[0], self.y[0])]
                      + list(zip(reversed(self.x), reversed(self.y))))
        # Create vertex coordinates for each grid cell...
        # (<0,0> is at the top left of the grid in this system)
        x, y = np.meshgrid(np.arange(nx), np.arange(ny))
        x, y = x.flatten(), y.flatten()
        points = np.vstack((x, y)).T

        roi_path = MplPath(poly_verts)
        mask = roi_path.contains_points(points).reshape((ny, nx))
        return mask

    def display_roi(self, **linekwargs):
        line = plt.Line2D(self.x + [self.x[0]], self.y + [self.y[0]],
                          color=self.color, **linekwargs)
        ax = plt.gca()
        ax.add_line(line)
        plt.draw()

    def get_mean_and_std(self, image):
        """Get statistics about pixel values of an image inside the ROI.

        Parameters
        ----------
        image: numpy array (2D)
            Image on which the statistics should be calculated

        Returns
        -------
        list of float:
            mean and standard deviation of the pixel values inside the ROI

        """
        mask = self.get_mask(image)
        mean = np.mean(np.extract(mask, image))
        std = np.std(np.extract(mask, image))
        return mean, std

    def display_mean(self, image, **textkwargs):
        """Display statistics about pixel values of an image inside the ROI.

        Parameters
        ----------
        image: numpy array (2D)
            Image on which the statistics should be calculated

        Returns
        -------
        None

        """
        mean, std = self.get_mean_and_std(image)
        string = "%.3f +- %.3f" % (mean, std)
        plt.text(self.x[0], self.y[0],
                 string, color=self.color,
                 bbox=dict(facecolor='w', alpha=0.6), **textkwargs)

    def get_roi_coordinates(self):
        """Get co-ordinates of the ROI polygon.

        Returns
        -------
        numpy array (2D)

        """
        roi_coordinates = list(zip(self.x, self.y))
        return roi_coordinates

    def __motion_notify_callback(self, event):
        if event.inaxes == self.ax:
            x, y = event.xdata, event.ydata
            if ((event.button is None or event.button == 1) and
                    self.line is not None):
                # Move line around
                x_data = [self.previous_point[0], x]
                y_data = [self.previous_point[1], y]
                logger.debug("draw line x: {} y: {}".format(x_data, y_data))
                self.line.set_data(x_data, y_data)
                self.fig.canvas.draw()

    def __button_press_callback(self, event):
        if event.inaxes == self.ax:
            x, y = event.xdata, event.ydata
            ax = event.inaxes
            if event.button == 1 and not event.dblclick:
                logger.debug("Received single left mouse button click")
                if self.line is None:  # If there is no line, create a line
                    self.line = plt.Line2D([x, x], [y, y],
                                           marker='o', color=self.color)
                    self.start_point = [x, y]
                    self.previous_point = self.start_point
                    self.x = [x]
                    self.y = [y]

                    ax.add_line(self.line)
                    self.fig.canvas.draw()
                    # Add a segment
                else:
                    # If there is a line, create a segment
                    x_data = [self.previous_point[0], x]
                    y_data = [self.previous_point[1], y]
                    logger.debug(
                        "draw line x: {} y: {}".format(x_data, y_data))
                    self.line = plt.Line2D(x_data, y_data,
                                           marker='o', color=self.color)
                    self.previous_point = [x, y]
                    self.x.append(x)
                    self.y.append(y)

                    event.inaxes.add_line(self.line)
                    self.fig.canvas.draw()

            elif (((event.button == 1 and event.dblclick) or
                   (event.button == 3 and not event.dblclick)) and
                  self.line is not None):
                # Close the loop and disconnect
                logger.debug("Received single right mouse button click or "
                             "double left click")
                if len(self.x) == 1 and len(self.y) == 1:
                    # If only one point is added, consider it as a single point ROI
                    self.completed = True
                else:
                    self.fig.canvas.mpl_disconnect(self.__cid1)
                    self.fig.canvas.mpl_disconnect(self.__cid2)

                    self.line.set_data([self.previous_point[0],
                                        self.start_point[0]],
                                       [self.previous_point[1],
                                        self.start_point[1]])
                    ax.add_line(self.line)
                    self.fig.canvas.draw()
                    self.line = None
                    self.completed = True

                if not sys.flags.interactive and self.close_figure:
                    #  Figure has to be closed so that code can continue
                    plt.close(self.fig)

    # For compatibility with old version
    def displayMean(self, *args, **kwargs):
        deprecation("Use 'display_mean' instead of 'displayMean'!")
        return self.display_mean(*args, **kwargs)

    def getMask(self, *args, **kwargs):
        deprecation("Use 'get_mask()' instead of 'getMask'!")
        return self.get_mask(*args, **kwargs)

    def displayROI(self, *args, **kwargs):
        deprecation("Use 'display_roi' instead of 'displayROI'!")
        return self.display_roi(*args, **kwargs)


class MultiRoi:
    def __init__(self,
                 fig=None, ax=None,
                 roi_names=None,
                 color_cycle=('b', 'g', 'r', 'c', 'm', 'y', 'k')
                 ):
        """

        Parameters
        ----------
        fig: matplotlib figure
            Figure on which to draw the ROIs
        ax: matplotlib axes
           Axes on which to draw the ROIs
        roi_names: list of str
            Optional names for the ROIs to draw.
            The ROIs can later be retrieved by using these names as keys for
            the `self.rois` dictionary. If None, consecutive numbers are used
            as ROI names
        color_cycle: list of str
            List of matplotlib colors for the ROIs
        """

        if fig is None:
            fig = plt.gcf()
        if ax is None:
            ax = fig.gca()

        self.color_cycle = color_cycle
        self.roi_names = roi_names
        self.fig = fig
        self.ax = ax
        self.rois = {}

        self.make_buttons()

    def make_buttons(self):
        ax_add_btn = plt.axes([0.7, 0.02, 0.1, 0.04])
        ax_finish_btn = plt.axes([0.81, 0.02, 0.1, 0.04])
        btn_finish = Button(ax_finish_btn, 'Finish')
        btn_finish.on_clicked(self.finish)
        btn_add = Button(ax_add_btn, 'New ROI')
        btn_add.on_clicked(self.add)
        plt.show(block=True)

    def add(self, event):
        """"Add a new ROI"""

        # Only draw a new ROI if the previous one is completed
        if self.rois:
            if not all(r.completed for r in self.rois.values()):
                return

        count = len(self.rois)
        idx = count % len(self.color_cycle)
        logger.debug("Creating new ROI {}".format(count))
        if self.roi_names is not None and idx < len(self.roi_names):
            roi_name = self.roi_names[idx]
        else:
            roi_name = str(count + 1)

        self.ax.set_title("Draw ROI '{}'".format(roi_name))
        plt.draw()
        roi = RoiPoly(color=self.color_cycle[idx],
                      fig=self.fig,
                      ax=self.ax,
                      close_fig=False,
                      show_fig=False)
        self.rois[roi_name] = roi

    def finish(self, event):
        logger.debug("Stop ROI drawing")
        plt.close(self.fig)


# For compatibility with old version
def roipoly(*args, **kwargs):
    deprecation("Import 'RoiPoly' instead of 'roipoly'!")
    return RoiPoly(*args, **kwargs)
