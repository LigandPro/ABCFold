import os
from pathlib import Path

from jinja2 import Template

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <title>{{ title }}</title>
    <meta http-equiv="content-type" content="application/xhtml+xml; charset=utf-8"/>
    <meta name="viewport" content="width=device-width, minimum-scale=1.0, maximum-scale=1.0"/>
    <meta name="theme-color" content="#ffffff">

    <link rel="icon" type="image/svg+xml" href="{{ favicon_svg }}">
    <link rel="icon" sizes="any" href="{{ favicon_ico }}" >

    <link rel="stylesheet" type="text/css" href="{{ bootstrap_min_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ bootstrap_css }}"/>

    <link rel="stylesheet" type="text/css" href="{{ pae_viewer_standalone_layout_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ common_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ structure_carousel_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ structure_viewer_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ structure_panel_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ pae_viewer_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ complex_sequence_viewer_css }}"/>
    <link rel="stylesheet" type="text/css" href="{{ pae_viewer_standalone_overrides_css }}"/>

    <script type="text/javascript" src="{{ jquery_min_js }}"></script>
    <script type="text/javascript" src="{{ jquery_ui_min_js }}"></script>
    <script type="text/javascript" src="{{ bootstrap_bundle_min_js }}"></script>
    <script type="text/javascript" src="{{ ngl_js }}"></script>
    <script type="text/javascript" src="{{ chroma_min_js }}"></script>
    <script type="text/javascript" src="{{ file_saver_min_js }}"></script>

    <script defer src="{{ setup_js }}"></script>

    <script defer type="module" src="{{ structure_carousel_js }}"></script>
    <script defer type="module" src="{{ pae_viewer_js }}"></script>
    <script defer type="module" src="{{ complex_sequence_viewer_js }}"></script>
</head>
<body>

<input type="hidden" id="relativePath" value="{{ relative_path }}">

<noscript>
    <div class="alert alert-danger text-center">
        <strong>Error:</strong> JavaScript is disabled or not supported
        by your browser, but this page requires it to work.
    </div>
</noscript>
<div id="container">
    <header id="top">
        <div class="title">{{ header_title }}</div>
        <div class="subtitle">{{ header_subtitle }}</div>
    </header>
    <main>
        {{ pae_viewer_demo_tpl }}
    </main>
    <footer class="footer">
        <div class="footer-segment">
            <h3>Contact</h3>
            <ul>
                {% for contact in contacts %}
                <li>
                    <a href="{{ contact.url }}" target="_blank">
                        {{ contact.name }}
                    </a>
                </li>
                {% endfor %}
            </ul>
        </div>
    </footer>
</div>
</body>
</html>
"""  # noqa


def render_html(args, output_file):

    template = Template(TEMPLATE)
    # create a relative link between the current directory and the template

    relative_path = Path(os.path.relpath(args.src_path, Path(output_file).parent))

    rendered_html = template.render(
        title=args.title,
        favicon_svg=str(relative_path.joinpath("standalone", "favicon.svg")),
        favicon_ico=str(relative_path.joinpath("standalone", "favicon.ico")),
        bootstrap_min_css=str(
            relative_path.joinpath("standalone", "libs", "bootstrap.min.css")
        ),
        bootstrap_css=str(
            relative_path.joinpath("standalone", "libs", "bootstrap@5.1.3.css")
        ),
        pae_viewer_standalone_layout_css=str(
            relative_path.joinpath("standalone", "css", args.standalonecss)
        ),
        common_css=str(relative_path.joinpath("standalone", "css", "common.css")),
        structure_carousel_css=str(
            relative_path.joinpath("src", "css", "structure-carousel.css")
        ),
        structure_viewer_css=str(
            relative_path.joinpath("src", "css", "structure-viewer.css")
        ),
        structure_panel_css=str(
            relative_path.joinpath("src", "css", "structure-panel.css")
        ),
        pae_viewer_css=str(relative_path.joinpath("src", "css", "pae-viewer.css")),
        complex_sequence_viewer_css=str(
            relative_path.joinpath("src", "css", "complex-sequence-viewer.css")
        ),
        pae_viewer_standalone_overrides_css=str(
            relative_path.joinpath(
                "standalone", "css", "paeViewerStandaloneOverrides.css"
            )
        ),
        jquery_min_js=str(
            relative_path.joinpath("standalone", "libs", "jquery.min.js")
        ),
        jquery_ui_min_js=str(
            relative_path.joinpath("standalone", "libs", "jquery-ui.min.js")
        ),
        bootstrap_bundle_min_js=str(
            relative_path.joinpath("standalone", "libs", "bootstrap.bundle.min.js")
        ),
        ngl_js=str(relative_path.joinpath("standalone", "libs", "ngl.js")),
        chroma_min_js=str(
            relative_path.joinpath("standalone", "libs", "chroma.min.js")
        ),
        file_saver_min_js=str(
            relative_path.joinpath("standalone", "libs", "FileSaver.min.js")
        ),
        setup_js=str(relative_path.joinpath("standalone", "js", "setup.js")),
        structure_carousel_js=str(
            relative_path.joinpath("src", "modules", "structure-carousel.js")
        ),
        pae_viewer_js=str(relative_path.joinpath("src", "modules", "pae-viewer.js")),
        complex_sequence_viewer_js=str(
            relative_path.joinpath("src", "modules", "complex-sequence-viewer.js")
        ),
        header_title=args.title,
        header_subtitle="Interactive display of the Predicted Aligned Error",
        relative_path=relative_path,
        pae_viewer_demo_tpl="{{paeViewerDemo.tpl}}",
        contacts=[
            {
                "url": "http://genmibio.uni-goettingen.de/",
                "name": "General Microbiology Göttingen",
            },
            {
                "url": "mailto:christoph.elfmann@uni-goettingen.de",
                "name": "Christoph Elfmann",
            },
            {"url": "mailto:jstuelk@gwdg.de", "name": "Jörg Stülke"},
        ],
    )

    return rendered_html


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "--output_file",
        help="Output file",
        type=str,
        default="pae-viewer.html",
    )

    parser.add_argument(
        "--title",
        help="Title of the HTML page",
        type=str,
        default="PAE Viewer",
    )
    parser.add_argument(
        "--standalonecss",
        type=str,
        default="paeViewerStandaloneLayout.css",
    )
    parser.add_argument(
        "--src_path",
        type=str,
        required=True,
    )

    args = parser.parse_args()
    rendered_html = render_html(args, output_file=args.output_file)

    # write html file
    with open(args.output_file, "w") as f:
        f.write(rendered_html)
