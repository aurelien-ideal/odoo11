#!/bin/bash

# Odoo extension creation tool, allow you to create an extension directory which can be imported directly in chrome

[ -d extension/static/src/css ] || mkdir -p extension/static/src/css

lessc static/src/less/import.less > static/src/css/project_timesheet.css

cp -r static extension
cp views/timesheet.html extension
cp manifest.json extension

cp ../web/static/src/js/boot.js extension/static/src/js

[ -d extension/static/src/js/core ] || mkdir extension/static/src/js/core
cp ../web/static/src/js/core/class.js extension/static/src/js/core
cp ../web/static/src/js/core/translation.js extension/static/src/js/core
cp ../web/static/src/js/core/time.js extension/static/src/js/core
cp ../web/static/src/js/core/ajax.js extension/static/src/js/core
cp ../web/static/src/js/core/widget.js extension/static/src/js/core
cp ../web/static/src/js/core/session.js extension/static/src/js/core
cp ../web/static/src/js/core/pyeval.js extension/static/src/js/core
cp ../web/static/src/js/core/utils.js extension/static/src/js/core
cp ../web/static/src/js/core/mixins.js extension/static/src/js/core
cp ../web/static/src/js/core/registry.js extension/static/src/js/core
cp ../web/static/src/js/core/local_storage.js extension/static/src/js/core
cp ../web/static/src/js/core/qweb.js extension/static/src/js/core
cp ../web/static/src/js/core/bus.js extension/static/src/js/core
cp ../web/static/src/js/core/rpc.js extension/static/src/js/core
cp ../web/static/src/js/core/context.js extension/static/src/js/core
cp ../web/static/src/js/core/concurrency.js extension/static/src/js/core
cp ../web/static/src/js/core/abstract_service.js extension/static/src/js/core

cp ../web/static/src/js/services/ajax_service.js extension/static/src/js/core
cp ../web/static/src/js/services/core.js extension/static/src/js/core

cp -r ../web/static/lib/qweb extension/static/lib
cp -r ../web/static/lib/nvd3 extension/static/lib
cp -r ../web/static/lib/jquery extension/static/lib
cp -r ../web/static/lib/jquery.ba-bbq extension/static/lib
cp -r ../web/static/lib/moment extension/static/lib
cp -r ../web/static/lib/underscore extension/static/lib
cp -r ../web/static/lib/underscore.string extension/static/lib
cp -r ../web/static/lib/py.js extension/static/lib
cp -r ../web/static/lib/fontawesome extension/static/lib

[ -d extension/static/lib/bootstrap/css ] || mkdir -p extension/static/lib/bootstrap/css
lessc ../web/static/lib/bootstrap/less/bootstrap.less > extension/static/lib/bootstrap/css/bootstrap.min.css

[ -d extension/static/lib/bootstrap/js ] || mkdir -p extension/static/lib/bootstrap/js
cp ../web/static/lib/bootstrap/js/modal.js extension/static/lib/bootstrap/js

echo "Extension created"
