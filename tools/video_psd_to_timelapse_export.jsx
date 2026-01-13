// PSD EXPORT TIMELAPSE FRAMES
// originally we were handling this in python psd tools but was slow
// for speed this exports in top down order hiding visible layers and saving each stage
// the result is the frames are in reverse order
#target photoshop
app.bringToFront();

// === GLOBAL VARIABLE FOR TARGET MAX DIMENSION ===
var TARGET_MAX_DIM = 1000; // Max allowed width/height in pixels (downscale only)

(function () {
    var __oldDialogs = app.displayDialogs;
    try {
        app.displayDialogs = DialogModes.NO;
    } catch (e) {}

    try {
        if (!app.documents.length) {
            return;
        }

        var doc = app.activeDocument;
        var psdName = decodeURI(doc.name.replace(/\.[^\.]+$/, "")); // Strip extension
        var parentFolder = decodeURI(doc.path); // Same folder as PSD
        var allLayers = [];
        collectLayers(doc, allLayers);

        // === RESIZE: ONLY DOWNSCALE IF LONGEST SIDE > TARGET_MAX_DIM ===
        try {
            var wPx = doc.width.as('px');
            var hPx = doc.height.as('px');
            var maxDim = Math.max(wPx, hPx);
            if (maxDim > TARGET_MAX_DIM) {
                if (wPx >= hPx) {
                    var newW = TARGET_MAX_DIM;
                    var newH = Math.round(hPx * (TARGET_MAX_DIM / wPx));
                    doc.resizeImage(UnitValue(newW, 'px'), UnitValue(newH, 'px'), null, ResampleMethod.BICUBIC);
                } else {
                    var newH2 = TARGET_MAX_DIM;
                    var newW2 = Math.round(wPx * (TARGET_MAX_DIM / hPx));
                    doc.resizeImage(UnitValue(newW2, 'px'), UnitValue(newH2, 'px'), null, ResampleMethod.BICUBIC);
                }
            }
        } catch (e) {
            // Fail quietly; continue export without resize
        }

        var visibleLayers = [];
        var originalVisibility = [];

        for (var i = 0; i < allLayers.length; i++) {
            var layer = allLayers[i];
            originalVisibility.push(layer.visible);
            if (layer.visible) {
                visibleLayers.push(layer);
            }
        }

        // Initial frame — before anything is hidden
        saveFrame(doc, parentFolder, 0);

        // Hide one additional layer from top to bottom and save each stage
        for (var i = 0; i < visibleLayers.length - 1; i++) {
            try {
                visibleLayers[i].visible = false;
            } catch (e) {}
            saveFrame(doc, parentFolder, i + 1);
        }

        // Restore visibility state
        for (var j = 0; j < allLayers.length; j++) {
            try {
                allLayers[j].visible = originalVisibility[j];
            } catch (e) {}
        }

    } catch (e) {
    } finally {
        try {
            app.displayDialogs = __oldDialogs;
        } catch (e2) {}
    }
})();

function collectLayers(parent, result) {
    for (var i = 0; i < parent.layers.length; i++) {
        var layer = parent.layers[i];
        if (layer.typename === "ArtLayer") {
            result.push(layer);
        } else if (layer.typename === "LayerSet") {
            collectLayers(layer, result);
        }
    }
}

function saveFrame(doc, folderPath, frameIndex) {
    var fileName = "psdtemp_" + padNumber(frameIndex, 5) + ".png";
    var file = new File(folderPath + "/" + fileName);
    var opts = new PNGSaveOptions();
    opts.compression = 9;
    opts.interlaced = false;
    doc.saveAs(file, opts, true, Extension.LOWERCASE);
}

function padNumber(n, digits) {
    var s = n.toString();
    while (s.length < digits) s = "0" + s;
    return s;
}
