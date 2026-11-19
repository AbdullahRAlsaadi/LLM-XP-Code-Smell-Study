def __init__(self, data, row=None, col=None, hue=None, col_wrap=None,
             sharex=True, sharey=True, size=3, aspect=1, palette=None,
             row_order=None, col_order=None, hue_order=None, hue_kws=None,
             dropna=True, legend_out=True, despine=True,
             margin_titles=False, xlim=None, ylim=None, subplot_kws=None,
             gridspec_kws=None):

    MPL_GRIDSPEC_VERSION = LooseVersion('1.4')
    OLD_MPL = LooseVersion(mpl.__version__) < MPL_GRIDSPEC_VERSION

    # Determine the hue facet layer information
    hue_var = hue
    if hue is None:
        hue_names = None
    else:
        hue_names = utils.categorical_order(data[hue], hue_order)

    colors = self._get_palette(data, hue, hue_order, palette)

    # Set up the lists of names for the row and column facet variables
    if row is None:
        row_names = []
    else:
        row_names = utils.categorical_order(data[row], row_order)

    if col is None:
        col_names = []
    else:
        col_names = utils.categorical_order(data[col], col_order)

    # Additional dict of kwarg -> list of values for mapping the hue var
    hue_kws = hue_kws if hue_kws is not None else {}

    # Make a boolean mask that is True anywhere there is an NA
    # value in one of the faceting variables, but only if dropna is True
    none_na = np.zeros(len(data), np.bool)
    if dropna:
        row_na = none_na if row is None else data[row].isnull()
        col_na = none_na if col is None else data[col].isnull()
        hue_na = none_na if hue is None else data[hue].isnull()
        not_na = ~(row_na | col_na | hue_na)
    else:
        not_na = ~none_na

    # Compute the grid shape
    ncol = 1 if col is None else len(col_names)
    nrow = 1 if row is None else len(row_names)
    self._n_facets = ncol * nrow

    self._col_wrap = col_wrap
    if col_wrap is not None:
        if row is not None:
            err = "Cannot use `row` and `col_wrap` together."
            raise ValueError(err)
        ncol = col_wrap
        nrow = int(np.ceil(len(data[col].unique()) / col_wrap))
    self._ncol = ncol
    self._nrow = nrow

    # Calculate the base figure size
    # This can get stretched later by a legend
    figsize = (ncol * size * aspect, nrow * size)

    # Validate some inputs
    if col_wrap is not None:
        margin_titles = False

    # Build the subplot keyword dictionary
    subplot_kws = {} if subplot_kws is None else subplot_kws.copy()
    gridspec_kws = {} if gridspec_kws is None else gridspec_kws.copy()
    if xlim is not None:
        subplot_kws["xlim"] = xlim
    if ylim is not None:
        subplot_kws["ylim"] = ylim

    # Initialize the subplot grid
    if col_wrap is None:
        kwargs = dict(figsize=figsize, squeeze=False,
                      sharex=sharex, sharey=sharey,
                      subplot_kw=subplot_kws,
                      gridspec_kw=gridspec_kws)

        if OLD_MPL:
            _ = kwargs.pop('gridspec_kw', None)
            if gridspec_kws:
                msg = "gridspec module only available in mpl >= {}"
                warnings.warn(msg.format(MPL_GRIDSPEC_VERSION))

        fig, axes = plt.subplots(nrow, ncol, **kwargs)
        self.axes = axes

    else:
        # If wrapping the col variable we need to make the grid ourselves
        if gridspec_kws:
            warnings.warn("`gridspec_kws` ignored when using `col_wrap`")

        n_axes = len(col_names)
        fig = plt.figure(figsize=figsize)
        axes = np.empty(n_axes, object)
        axes[0] = fig.add_subplot(nrow, ncol, 1, **subplot_kws)
        if sharex:
            subplot_kws["sharex"] = axes[0]
        if sharey:
            subplot_kws["sharey"] = axes[0]
        for i in range(1, n_axes):
            axes[i] = fig.add_subplot(nrow, ncol, i + 1, **subplot_kws)
        self.axes = axes

        # Now we turn off labels on the inner axes
        if sharex:
            for ax in self._not_bottom_axes:
                for label in ax.get_xticklabels():
                    label.set_visible(False)
                ax.xaxis.offsetText.set_visible(False)
        if sharey:
            for ax in self._not_left_axes:
                for label in ax.get_yticklabels():
                    label.set_visible(False)
                ax.yaxis.offsetText.set_visible(False)

    # Set up the class attributes
    # ---------------------------

    # First the public API
    self.data = data
    self.fig = fig
    self.axes = axes

    self.row_names = row_names
    self.col_names = col_names
    self.hue_names = hue_names
    self.hue_kws = hue_kws

    # Next the private variables
    self._nrow = nrow
    self._row_var = row
    self._ncol = ncol
    self._col_var = col

    self._margin_titles = margin_titles
    self._col_wrap = col_wrap
    self._hue_var = hue_var
    self._colors = colors
    self._legend_out = legend_out
    self._legend = None
    self._legend_data = {}
    self._x_var = None
    self._y_var = None
    self._dropna = dropna
    self._not_na = not_na

    # Make the axes look good
    fig.tight_layout()
    if despine:
        self.despine()
