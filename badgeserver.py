#!/usr/bin/python
"""
Script to dynamically generate a status shield.

Needs python-lxml and python-cairosvg (sudo apt-get install it).

Be sure to install the Open Sans font where cairo will find it
(i.e. cp font/Open_Sans/*.ttf ~/.local/share/fonts/).
"""

import os

from lxml import etree
from cairosvg import svg2png


HERE = os.path.dirname(__file__)
SVG_TEMPLATE_FILE = os.path.join(HERE, "shield.svg")


def make_badge_svg(color="lightgray"):
    with open(SVG_TEMPLATE_FILE) as f:
        svg = f.read()
    tree = etree.fromstring(svg)
    nsmap = dict(svg='http://www.w3.org/2000/svg')
    for node in tree.xpath('//svg:g[@id="status"]/svg:rect | '
                           '//svg:g[@id="status"]/svg:path', namespaces=nsmap):
        node.attrib['fill'] = "url(#%s)" % color
    svg = etree.tostring(tree)
    return svg


def make_badge_png(**kw):
    svg = make_badge_svg(**kw)
    return svg2png(svg)


def wsgi_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'image/png')]
    start_response(status, headers)
    return [make_badge_png(color='green')]


def serve(port=8000, listen_on='localhost'):
    from wsgiref.simple_server import make_server
    server = make_server(listen_on, port, wsgi_app)
    print("Listening on http://%s:%d/" % (listen_on or '*', port))
    server.serve_forever()


def main():
    serve()


if __name__ == '__main__':
    main()
