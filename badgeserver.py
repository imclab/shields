#!/usr/bin/python
"""
Script to dynamically generate a status shield.

Needs python-lxml and python-cairosvg (sudo apt-get install it).

Be sure to install the Open Sans font where cairo will find it
(i.e. cp font/Open_Sans/*.ttf ~/.local/share/fonts/).
"""

import os
import cgi
from functools import partial
from cStringIO import StringIO

from lxml import etree
from cairosvg import svg2png


HERE = os.path.dirname(__file__)
SVG_TEMPLATE_FILE = os.path.join(HERE, "shield.svg")


def make_badge_svg(vendor="vendor", status="status", color="lightgray"):
    with open(SVG_TEMPLATE_FILE) as f:
        svg = f.read()
    tree = etree.fromstring(svg)
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
    # change the status text
    for node in xpath('//svg:g[@id="status"]/svg:text'):
        node.text = status
    return etree.tostring(tree)


def make_badge_png(**kw):
    svg = make_badge_svg(**kw)
    return svg2png(svg)


def wsgi_app(environ, start_response):
    # Parse query string
    form = cgi.FieldStorage(environ=environ, fp=StringIO())
    vendor = form.getfirst("vendor", "badgeserver")
    status = form.getfirst("status", "okay")
    color = form.getfirst("color", "lightgray")
    format = form.getfirst("format", "png")
    # Generate the image
    factory, content_type = dict(
        png=(make_badge_png, "image/png"),
        svg=(make_badge_svg, "image/svg+xml"),
    )[format]
    image_data = factory(vendor=vendor, status=status, color=color)
    # Return a response
    status = '200 OK'
    headers = [('Content-type', content_type)]
    start_response(status, headers)
    return [image_data]


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
