// PSD EXPORT TIMELAPSE FRAMES
// originally we were handling this in python psd tools but was sloe
// for speed this exports in top down order hiding visible layers and saving each stage
// the result is the frames are in reverse order
#target photoshop
app.bringToFront();

// === GLOBAL VARIABLE FOR TARGET HEIGHT ===
var TARGET_HEIGHT = 1000; // Resize height in pixels

(function () {
    if (!app.documents.length) {
        alert("No PSD is currently open.");
        return;
    }

    var doc = app.activeDocument;
    var psdName = decodeURI(doc.name.replace(/\.[^\.]+$/, "")); // Strip extension
    var parentFolder = decodeURI(doc.path); // Same folder as PSD
    var allLayers = [];
    collectLayers(doc, allLayers);

    // === RESIZE TO TARGET HEIGHT, PROPORTIONAL WIDTH ===
    if (doc.height != TARGET_HEIGHT) {
        doc.resizeImage(null, UnitValue(TARGET_HEIGHT, "px"), null, ResampleMethod.BICUBIC);
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

    // === CLOSE DOCUMENT WITHOUT SAVING, NO PROMPT ===
    doc.close(SaveOptions.DONOTSAVECHANGES);
    // (No alert or message prompt)
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
