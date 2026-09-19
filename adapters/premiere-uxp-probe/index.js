"use strict";

const PROJECT_NAME = "motion-engine-premiere-probe.prproj";
const PLATE_NAME = "synthetic-plate.png";
const SEQUENCE_NAME = "Motion Engine Probe";
const MARKER_NAME = "Beat 1";
const REPORT_NAME = "motion-engine-premiere-probe-report.json";

function requireResult(value, message) {
  if (!value) throw new Error(message);
  return value;
}

async function runProbe(ppro, fileSystem) {
  const destination = await fileSystem.getFolder();
  if (!destination) return { status: "cancelled" };

  const entries = await destination.getEntries();
  if (entries.some((entry) => [PROJECT_NAME, REPORT_NAME].includes(entry.name.toLowerCase()))) {
    throw new Error("A probe project or report already exists here. Choose a fresh folder.");
  }

  const pluginFolder = await fileSystem.getPluginFolder();
  const plate = (await pluginFolder.getEntries()).find((entry) => entry.name === PLATE_NAME);
  requireResult(plate && plate.isFile, `Plugin sample ${PLATE_NAME} is missing.`);

  const projectPath = `${destination.nativePath}/${PROJECT_NAME}`;
  const platePath = plate.nativePath;
  const project = requireResult(await ppro.Project.createProject(projectPath), "Project creation failed.");
  const root = await project.getRootItem();
  requireResult(await project.importFiles([platePath], true, root, false), "Media import failed.");

  const imported = (await root.getItems()).find((item) => item.name === PLATE_NAME);
  requireResult(imported, "Imported plate is missing from the project bin.");
  const clip = requireResult(ppro.ClipProjectItem.cast(imported), "Imported plate is not a clip.");
  requireResult(!(await clip.isOffline()), "Imported plate is offline.");

  // This API inserts the selected media while creating the sequence.
  const sequence = requireResult(
    await project.createSequenceFromMedia(SEQUENCE_NAME, [clip], root),
    "Sequence creation failed."
  );
  const markers = await ppro.Markers.getMarkers(sequence);
  const markerTime = ppro.TickTime.createWithSeconds(1);
  const markerDuration = ppro.TickTime.createWithSeconds(0);
  let committed = false;
  project.lockedAccess(() => {
    committed = project.executeTransaction((compoundAction) => {
      compoundAction.addAction(markers.createAddMarkerAction(
        MARKER_NAME, "Comment", markerTime, markerDuration, "Motion Engine public compatibility probe"
      ));
    }, "Add probe marker");
  });
  requireResult(committed, "Marker transaction failed.");
  requireResult(await project.save(), "Project save failed.");
  requireResult(await project.close(), "Project close failed.");

  const reopened = requireResult(await ppro.Project.open(projectPath), "Saved project could not be reopened.");
  const sequences = await reopened.getSequences();
  const reopenedSequence = requireResult(
    sequences.find((item) => item.name === SEQUENCE_NAME), "Sequence was lost after reopen."
  );
  const videoTrack = requireResult(await reopenedSequence.getVideoTrack(0), "Video track 0 is missing.");
  const trackItems = videoTrack.getTrackItems(ppro.Constants.TrackItemType.CLIP, false);
  requireResult(trackItems.length === 1, `Expected one video clip; found ${trackItems.length}.`);
  requireResult((await trackItems[0].getProjectItem()).name === PLATE_NAME, "Wrong media on video track.");

  const reopenedMarkers = await ppro.Markers.getMarkers(reopenedSequence);
  const beatMarkers = reopenedMarkers.getMarkers().filter((item) => item.getName() === MARKER_NAME);
  requireResult(beatMarkers.length === 1, "Probe marker was lost after reopen.");
  requireResult(beatMarkers[0].getStart().ticks === markerTime.ticks, "Probe marker moved after reopen.");

  const reopenedRoot = await reopened.getRootItem();
  const reopenedItem = requireResult(
    (await reopenedRoot.getItems()).find((item) => item.name === PLATE_NAME),
    "Imported media was lost after reopen."
  );
  const reopenedClip = ppro.ClipProjectItem.cast(reopenedItem);
  requireResult(!(await reopenedClip.isOffline()), "Imported media is offline after reopen.");
  const mediaPath = await reopenedClip.getMediaFilePath();
  requireResult(mediaPath.replace(/\\/g, "/").toLowerCase() === platePath.replace(/\\/g, "/").toLowerCase(),
    "Media link changed after reopen.");

  const result = { status: "PASS", projectPath, sequence: SEQUENCE_NAME, videoClips: 1,
    marker: MARKER_NAME, markerTicks: markerTime.ticks, mediaPath };
  const report = await destination.createFile(REPORT_NAME, { overwrite: false });
  await report.write(JSON.stringify(result, null, 2));
  return result;
}

async function command() {
  try {
    const result = await runProbe(require("premierepro"), require("uxp").storage.localFileSystem);
    console.log("Motion Engine Premiere probe: " + JSON.stringify(result));
  } catch (error) {
    console.error("Motion Engine Premiere probe failed:", error);
  }
}

if (typeof module !== "undefined") module.exports = { runProbe };
if (typeof require === "function") {
  try {
    require("uxp").entrypoints.setup({ commands: { runProbe: command } });
  } catch (error) {
    // Node tests do not provide the UXP host; Premiere does.
    if (error.code !== "MODULE_NOT_FOUND") throw error;
  }
}
