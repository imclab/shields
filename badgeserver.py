#!/usr/bin/python
"""
Script to dynamically generate a status shield.

Needs python-lxml and python-cairosvg (sudo apt-get install it).

Be sure to install the Open Sans font where cairo will find it
(i.e. cp font/Open_Sans/*.ttf ~/.local/share/fonts/).
"""

import cgi
import os
import re
import shutil
import subprocess
import tempfile
from cStringIO import StringIO
from contextlib import contextmanager
from functools import partial

import cairo
from cairosvg import svg2png as svg2png_cairosvg
from lxml import etree


HERE = os.path.dirname(__file__)
SVG_TEMPLATE_FILE = os.path.join(HERE, "shield.svg")


@contextmanager
def TemporaryDirectory():
    tmpdir = tempfile.mkdtemp(prefix='badgeserver-')
    orig_dir = os.getcwd()
    os.chdir(tmpdir)
    try:
        yield
    finally:
        os.chdir(orig_dir)
        shutil.rmtree(tmpdir)


def svg2png_command(svg_data, command):
    with TemporaryDirectory():
        with open('badge.svg', 'wb') as f:
            f.write(svg_data)
        subprocess.check_call(command)
        with open('badge.png', 'rb') as f:
            return f.read()

def svg2png_inkscape(svg_data):
    return svg2png_command(svg_data, ['inkscape', '-f', 'badge.svg', '-e', 'badge.png'])


def svg2png_imagemagick(svg_data):
    return svg2png_command(svg_data, ['convert', 'badge.svg', 'badge.png'])


def load_svg_template():
    with open(SVG_TEMPLATE_FILE) as f:
        return f.read()


def list_color_options():
    tree = etree.fromstring(load_svg_template())
    nsmap = dict(svg='http://www.w3.org/2000/svg')
    xpath = partial(tree.xpath, namespaces=nsmap)
    return [node.attrib['id'] for node in xpath('//svg:linearGradient')]


def text_width(text, font_family="Open Sans", font_size=10,
               font_style=cairo.FONT_SLANT_NORMAL,
               font_weight=cairo.FONT_WEIGHT_NORMAL):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    context = cairo.Context(surface)
    context.select_font_face(font_family, font_style, font_weight)
    context.set_font_size(font_size)
    return context.text_extents(text)[2]


def svg_text_node_width(node):
    # XXX: requires that the node have font-family and font-size attributes
    # (I believe SVG defaults to sans-serif 12pt)
    # XXX: ignores font-style and font-weight attributes
    # (see cairosvg/surface/text.py about handling those)
    font_family = node.attrib['font-family']
    font_size = int(node.attrib['font-size'])
    return text_width(node.text, font_family, font_size)


def make_badge_svg(vendor="vendor", status="status", color="lightgray",
                   vendor_width=40, status_width=37):
    tree = etree.fromstring(load_svg_template())
    nsmap = dict(svg='http://www.w3.org/2000/svg')
    xpath = partial(tree.xpath, namespaces=nsmap)
    # change status background gradient
    if not xpath('//svg:linearGradient[@id="%s"]' % color):
        print("There's no gradient for %s" % color)
    for node in xpath('//svg:g[@id="status"]/*[@fill="url(#lightgray)"]'):
        node.attrib['fill'] = "url(#%s)" % color
    # change the vendor text
    for node in xpath('//svg:g[@id="vendor"]/svg:text'):
        node.text = vendor
        if vendor_width < 0:
            vendor_width = svg_text_node_width(node) + 7
    # change the status text
    for node in xpath('//svg:g[@id="status"]/svg:text'):
        node.text = status
        if status_width < 0:
            status_width = svg_text_node_width(node) + 7
    # change the vendor and status widths
    for node in xpath('//svg:g[@id="vendor"]/svg:rect'):
        node.attrib['width'] = str(vendor_width)
    for node in xpath('//svg:g[@id="status"]/svg:rect'):
        node.attrib['x'] = str(vendor_width + 3)
        node.attrib['width'] = str(status_width)
    for node in xpath('//svg:g[@id="status"]/svg:text'):
        node.attrib['x'] = str(vendor_width + 7)
    for node in xpath('//svg:g[@id="status"]/svg:path'):
        node.attrib['d'] = re.sub(r'^M\d+',
                                  'M%d' % (vendor_width + status_width + 6),
                                  node.attrib['d'])
    for node in xpath('/svg:svg'):
        node.attrib['width'] = str(vendor_width + status_width + 6)
    return etree.tostring(tree)


def make_badge_png(**kw):
    converter = kw.pop('converter', None) or 'cairosvg'
    svg = make_badge_svg(**kw)
    svg2png = {
        'cairosvg': svg2png_cairosvg,
        'inkscape': svg2png_inkscape,
        'imagemagick': svg2png_imagemagick,
    }[converter]
    return svg2png(svg)


def render_html(html):
    status = '200 OK'
    headers = [('Content-type', 'text/html; charset=UTF-8')]
    return status, headers, html


def render_error(code, message):
    status = '%d %s' % (code, message)
    headers = [('Content-type', 'text/plain; charset=UTF-8')]
    return status, headers, message


def render_image(form, format):
    vendor = form.getfirst("vendor", "badgeserver").decode('UTF-8')
    vendor_width = int(form.getfirst("vendor_width", "-1"))
    status = form.getfirst("status", "okay").decode('UTF-8')
    status_width = int(form.getfirst("status_width", "-1"))
    color = form.getfirst("color", "lightgray")
    converter = form.getfirst("converter", "")
    factory, content_type = dict(
        png=(make_badge_png, "image/png"),
        svg=(make_badge_svg, "image/svg+xml"),
    )[format]
    image_data = factory(vendor=vendor, status=status, color=color,
                         vendor_width=vendor_width, status_width=status_width,
                         converter=converter)
    status = '200 OK'
    headers = [('Content-type', content_type)]
    return status, headers, image_data


INDEX_HTML = '''\
<!DOCTYPE html>
<html>
  <head>
    <title>Status shield generator</title>
    <style type="text/css">
      body {
        padding: 2em;
      }
      label {
        display: inline-block;
        text-align: right;
        width: 3em;
        margin-right: 1ex;
      }
      p {
        margin: 1ex;
      }
      form {
        margin-bottom: 2em;
      }
      input[type="number"] {
        width: 4em;
      }
    </style>
    <script type="text/javascript">
      function update() {
        var vendor = document.getElementById("vendor").value;
        var vendor_width = document.getElementById("vendor_width").value;
        var status = document.getElementById("status").value;
        var status_width = document.getElementById("status_width").value;
        var color = document.getElementById("color").value;
        var format = document.getElementById("format").value;
        var converter = document.getElementById("converter").value;
        var img = document.getElementById("result");
        img.src = "/image." + format + "?vendor=" + vendor + "&status=" + status + "&color=" + color + "&vendor_width=" + vendor_width + "&status_width=" + status_width + "&converter=" + converter;
      }
    </script>
  </head>
  <body onload="update()">
    <form>
      <p>
        <label for="vendor">Vendor</label>
        <input id="vendor" type="text" name="vendor" value="vendor" onchange="update()" onkeyup="update()">
        <input id="vendor_width" type="number" name="vendor_width" value="-1" onchange="update()">px (-1 = auto)
      </p>
      <p>
        <label for="status">Status</label>
        <input id="status" type="text" name="status" value="status" onchange="update()" onkeyup="update()">
        <input id="status_width" type="number" name="status_width" value="-1" onchange="update()">px (-1 = auto)
      </p>
      </p>
      <p>
        <label for="status">Color</label>
        <select id="color" name="color" onchange="update()">
          %(color_options)s
        </select>
      </p>
      <p>
        <label for="status">Format</label>
        <select id="format" name="format" onchange="update()">
          <option value="png">PNG</option>
          <option value="svg">SVG</option>
        </select>
      </p>
      <p>
        <label for="status">SVG converter</label>
        <select id="converter" name="converter" onchange="update()">
          <option value="cairosvg">CairoSVG</option>
          <option value="inkscape">Inkscape</option>
          <option value="imagemagick">ImageMagick</option>
        </select>
      </p>
      <p>
        <input type="submit" value="Update" onclick="update(); return false">
      </p>
    </form>
    <p><img id="result" src="/image.png?vendor=vendor&amp;status=status&amp;color=lightgray"></p>
  </body>
</html>
'''


def wsgi_app(environ, start_response):
    # Parse the request
    path = environ['PATH_INFO']
    form = cgi.FieldStorage(environ=environ, fp=StringIO())
    # Dispatch to the right handler
    if path == '/':
        status, headers, body = render_html(INDEX_HTML % dict(
            color_options=''.join(
                '<option>%s</option>' % color
                for color in list_color_options()
                if color != 'gray'),
        ))
    elif path == '/image.png':
        status, headers, body = render_image(form, "png")
    elif path == '/image.svg':
        status, headers, body = render_image(form, "svg")
    else:
        status, headers, body = render_error(404, "Not found")
    start_response(status, headers)
    return [body]


def serve(port=8000, listen_on='localhost'):
    from wsgiref.simple_server import make_server
    server = make_server(listen_on, port, wsgi_app)
    print("Listening on http://%s:%d/" % (listen_on or '*', port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    serve()


if __name__ == '__main__':
    main()
