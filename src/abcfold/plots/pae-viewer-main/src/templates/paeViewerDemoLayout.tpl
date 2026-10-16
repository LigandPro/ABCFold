<!doctype html>
<html lang="en">
  <head>
    <title>{{:pageTitle}}</title>
    <base href="<?php echo $GLOBALS['WEBROOT'];?>/" />

    <meta http-equiv="expires" content="0" />
    <meta http-equiv="content-type" content="application/xhtml+xml; charset=utf-8" />
    <meta name="viewport" content="width=device-width, minimum-scale=1.0, maximum-scale=1.0" />

    <link rel="icon" href="{{@img/pae-demo/favicon.svg}}" type="image/svg+xml">
    <link rel="icon" href="{{@img/pae-demo/favicon.ico}}" sizes="any">

    <link rel="apple-touch-icon" href="{{@img/apple-touch-icon.png}}">
    <link rel="manifest" href="{{@manifest.json}}"> <!-- manifest currently not accessible -->
    <meta name="theme-color" content="#ffffff">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-rbsA2VBKQhggwzxH7pPCaAqO46MgnOM80zW1RWuH61DGLwZJEdK2Kadq2F9CUG65"
          crossorigin="anonymous">


    <!-- html5 + CSS 3 Template created by miss monorom  http://intensivstation.ch 2013 -->
    <link rel="stylesheet" href="{{@css/paeViewerDemoLayout.css}}" type="text/css" />
    <link rel="stylesheet" href="{{@css/common.css}}" type="text/css" />


    <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
    <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.12.1/jquery-ui.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"
            integrity="sha384-kenU1KFdBIe4zVF0s0G1M5b4hcpxyD9F7jL+jjXkk+Q2h455rYXK/7HAuoJl+0I4"
            crossorigin="anonymous"></script>
    <script type="text/javascript" src="https://unpkg.com/ngl@2.0.1/dist/ngl.js"></script>
    <script type="text/javascript" src="{{@js/libs/chroma.min.js}}"></script>
    <script type="text/javascript" src="{{@js/libs/FileSaver.min.js}}"></script>

    {{css:css}}
    {{modules:modules}}
    {{js:jsBeforeContent}}

    <link rel="stylesheet" href="{{@css/paeViewerDemoOverrides.css}}" type="text/css" />
  </head>
  <body>
    <div id="container">
      <div id="top">
          <div class="title">PAE Viewer</div>
          <div class="subtitle">Interactive display of the Predicted Aligned Error</div>
      </div>
      <section id="content">
        <div id="content-wrapper">
          {{:currentBannerDisplay}}
          <h1>
            <span>{{:title}}</span>
            <span style="float:right; font-size: smaller">{{:titleExtra}}</span>
          </h1>
          {{:content}}
        </div>
      </section>
      <footer class="footer">
        <div class="footer-segment">
          <h3>Contact</h3>
          <ul>
            <li>
              <a href="http://genmibio.uni-goettingen.de/" target="_blank">
                General Microbiology Göttingen
              </a>
            </li>
            <li>Web admin: <a href="mailto:christoph.elfmann@uni-goettingen.de">Christoph Elfmann</a></li>
            <li>Admin: <a href="mailto:jstuelk@gwdg.de">Jörg Stülke</a></li>
          </ul>
        </div>
      </footer>
    </div><!-- container -->
      <script type="text/javascript">{{:jsvars}}</script>
      <script type="text/javascript" src="{{@js/search.js}}"></script>
    <script type="text/javascript" src="{{@js/user.js}}"></script>
    <script type="text/javascript" src="{{@js/pubmed.js}}"></script>
    <script type="text/javascript" src="{{@js/layout1.js}}"></script>
    {{js:jsAfterContent}}
  </body>
</html>
