"""Functions for easy interactions with IPython and IPython notebooks."""

from __future__ import absolute_import

import io
import os
import uuid

import numpy as np

try:
    import IPython
    from IPython import get_ipython
    from IPython.display import HTML

    if IPython.version_info[0] <= 3:
        from IPython.config import Config
        from IPython.nbconvert import HTMLExporter, PythonExporter
    else:
        from traitlets.config import Config
        from nbconvert import HTMLExporter, PythonExporter

    # nbformat.current deprecated in IPython 3.0
    if IPython.version_info[0] <= 2:
        # pylint: disable=ungrouped-imports
        from IPython.nbformat import current

        def read_nb(fp):
            return current.read(fp, 'json')
    else:
        if IPython.version_info[0] == 3:
            # pylint: disable=ungrouped-imports
            from IPython import nbformat
        else:
            import nbformat

        def read_nb(fp):
            # Have to load as version 4 or running notebook fails
            return nbformat.read(fp, 4)
except ImportError:
    def get_ipython():
        return None
assert get_ipython


def check_ipy_version(min_version):
    try:
        import IPython
        return IPython.version_info >= min_version
    except ImportError:
        return False


def has_ipynb_widgets():
    """Determines whether IPython widgets are available.

    Returns
    -------
    bool
        ``True`` if IPython widgets are available, otherwise ``False``.
    """
    try:
        if IPython.version_info[0] <= 3:
            from IPython.html import widgets as ipywidgets
            from IPython.utils import traitlets
        else:
            import ipywidgets
            import traitlets
        assert ipywidgets
        assert traitlets
    except ImportError:
        return False
    else:
        return True


def hide_input():
    """Hide the input of the Jupyter notebook input block this is executed in.

    Returns a link to toggle the visibility of the input block.
    """
    uuid = np.random.randint(np.iinfo(np.int32).max)

    script = """
        <a id="%(uuid)s" href="javascript:toggle_input_%(uuid)s()"
          >Show Input</a>

        <script type="text/javascript">
        var toggle_input_%(uuid)s;
        (function() {
            if (typeof jQuery == 'undefined') {
                // no jQuery
                var link_%(uuid)s = document.getElementById("%(uuid)s");
                var cell = link_%(uuid)s;
                while (cell.className.split(' ')[0] != "cell"
                       && cell.className.split(' ')[0] != "nboutput") {
                    cell = cell.parentNode;
                }
                var input_%(uuid)s;
                if (cell.className.split(' ')[0] == "cell") {
                    for (var i = 0; i < cell.children.length; i++) {
                        if (cell.children[i].className.split(' ')[0]
                            == "input") {
                            input_%(uuid)s = cell.children[i];
                        }
                    }
                } else {
                    input_%(uuid)s = cell.previousElementSibling;
                }
                input_%(uuid)s.style.display = "none"; // hide

                toggle_input_%(uuid)s = function() {
                    if (input_%(uuid)s.style.display == "none") {
                        input_%(uuid)s.style.display = ""; // show
                        link_%(uuid)s.innerHTML = "Hide Input";
                    } else {
                        input_%(uuid)s.style.display = "none"; // hide
                        link_%(uuid)s.innerHTML = "Show Input";
                    }
                }

            } else {
                // jQuery
                var link_%(uuid)s = $("a[id='%(uuid)s']");
                var cell_%(uuid)s = link_%(uuid)s.parents("div.cell:first");
                if (cell_%(uuid)s.length == 0) {
                    cell_%(uuid)s = link_%(uuid)s.parents(
                        "div.nboutput:first");
                }
                var input_%(uuid)s = cell_%(uuid)s.children("div.input");
                if (input_%(uuid)s.length == 0) {
                    input_%(uuid)s = cell_%(uuid)s.prev("div.nbinput");
                }
                input_%(uuid)s.hide();

                toggle_input_%(uuid)s = function() {
                    if (input_%(uuid)s.is(':hidden')) {
                        input_%(uuid)s.slideDown();
                        link_%(uuid)s[0].innerHTML = "Hide Input";
                    } else {
                        input_%(uuid)s.slideUp();
                        link_%(uuid)s[0].innerHTML = "Show Input";
                    }
                }
            }
        }());
        </script>
    """ % dict(uuid=uuid)

    return HTML(script)


def load_notebook(nb_path):
    with io.open(nb_path, 'r', encoding='utf-8') as f:
        nb = read_nb(f)
    return nb


def export_py(nb, dest_path=None):
    """Convert notebook to Python script.

    Optionally saves script to dest_path.
    """
    exporter = PythonExporter()
    body, resources = exporter.from_notebook_node(nb)

    # Remove all lines with get_ipython
    while u"get_ipython()" in body:
        ind0 = body.find(u"get_ipython()")
        ind1 = body.find(u"\n", ind0)
        body = body[:ind0] + body[(ind1 + 1):]

    if u"plt" in body:
        body += u"\nplt.show()\n"

    if dest_path is not None:
        with io.open(dest_path, 'w', encoding='utf-8') as f:
            f.write(body)
    return body


def export_html(nb, dest_path=None, image_dir=None, image_rel_dir=None):
    """Convert notebook to HTML.

    Optionally saves HTML to dest_path.
    """
    c = Config({'ExtractOutputPreprocessor': {'enabled': True}})

    exporter = HTMLExporter(template_file='full', config=c)
    output, resources = exporter.from_notebook_node(nb)
    header = output.split('<head>', 1)[1].split('</head>', 1)[0]
    body = output.split('<body>', 1)[1].split('</body>', 1)[0]

    # Monkeypatch CSS
    header = header.replace('<style', '<style scoped="scoped"')
    header = header.replace(
        'body {\n  overflow: visible;\n  padding: 8px;\n}\n', '')
    header = header.replace("code,pre{", "code{")

    # Filter out styles that conflict with the sphinx theme.
    bad_anywhere = ['navbar',
                    'body{',
                    'alert{',
                    'uneditable-input{',
                    'collapse{']
    bad_anywhere.extend(['h%s{' % (i+1) for i in range(6)])

    bad_beginning = ['pre{', 'p{margin']

    header_lines = [x for x in header.split('\n')
                    if (not any(x.startswith(s) for s in bad_beginning)
                        and not any(s in x for s in bad_anywhere))]
    header = '\n'.join(header_lines)

    # Concatenate raw html lines
    lines = ['<div class="ipynotebook">']
    lines.append(header)
    lines.append(body)
    lines.append('</div>')
    html_out = '\n'.join(lines)

    if image_dir is not None and image_rel_dir is not None:
        html_out = export_images(resources, image_dir, image_rel_dir, html_out)

    if dest_path is not None:
        with io.open(dest_path, 'w', encoding='utf-8') as f:
            f.write(html_out)
    return html_out


def export_images(resources, image_dir, image_rel_dir, html_out):
    my_uuid = uuid.uuid4().hex

    for output in resources['outputs']:
        fname = "%s%s" % (my_uuid, output)
        new_path = os.path.join(image_dir, fname)
        new_rel_path = os.path.join(image_rel_dir, fname)
        html_out = html_out.replace(output, new_rel_path)
        with open(new_path, 'wb') as f:
            f.write(resources['outputs'][output])
    return html_out


def iter_cells(nb, cell_type="code"):
    if nb.nbformat <= 3:
        cells = []
        for ws in nb.worksheets:
            cells.extend(ws.cells)
    else:
        cells = nb.cells

    for cell in cells:
        if cell.cell_type == cell_type:
            yield cell
