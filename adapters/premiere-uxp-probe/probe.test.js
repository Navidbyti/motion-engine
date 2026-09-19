"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const { runProbe } = require("./index.js");

function fixture({ existing = [], loseMarker = false } = {}) {
  const image = { name: "synthetic-plate.png", nativePath: "C:/plugin/synthetic-plate.png", isFile: true };
  const destination = {
    nativePath: "C:/scratch",
    getEntries: async () => existing.map((name) => ({ name })),
    createFile: async () => ({ write: async (data) => { destination.report = JSON.parse(data); } })
  };
  const fs = {
    getFolder: async () => destination,
    getPluginFolder: async () => ({ getEntries: async () => [image] })
  };
  const marker = { getName: () => "Beat 1", getStart: () => ({ ticks: "1000" }) };
  const markers = {
    createAddMarkerAction: () => ({ marker }),
    getMarkers: () => loseMarker ? [] : [marker]
  };
  const imported = {
    name: image.name,
    isOffline: async () => false,
    getMediaFilePath: async () => image.nativePath
  };
  const root = { getItems: async () => [imported] };
  const videoTrack = {
    getTrackItems: () => [{ getProjectItem: async () => imported }]
  };
  const settings = { setVideoFrameRate: () => true, getVideoFrameRate: () => ({ value: 30 }) };
  const sequence = { name: "Motion Engine Probe", getVideoTrack: async () => videoTrack,
    getSettings: async () => settings, createSetSettingsAction: () => ({}) };
  const project = {
    getRootItem: async () => root,
    importFiles: async () => true,
    createSequenceFromMedia: async () => sequence,
    lockedAccess: (callback) => callback(),
    executeTransaction: (callback) => { callback({ addAction: () => {} }); return true; },
    save: async () => true,
    close: async () => true,
    getSequences: async () => [sequence]
  };
  const ppro = {
    Project: { createProject: async () => project, open: async () => project },
    ClipProjectItem: { cast: (item) => item },
    Markers: { getMarkers: async () => markers },
    FrameRate: { createWithValue: (value) => ({ value }) },
    TickTime: { createWithSeconds: (seconds) => ({ ticks: String(seconds * 1000) }),
      createWithFrameAndFrameRate: (frames, frameRate) => ({ ticks: String(frames * 1000 / frameRate.value) }) },
    Constants: { TrackItemType: { CLIP: 1 } }
  };
  return { fs, ppro, destination };
}

test("reopens and verifies media and marker before reporting PASS", async () => {
  const { fs, ppro, destination } = fixture();
  const result = await runProbe(ppro, fs);
  assert.equal(result.status, "PASS");
  assert.equal(destination.report.markerTicks, "1000");
  assert.equal(destination.report.videoClips, 1);
});

test("refuses to replace an existing project", async () => {
  const { fs, ppro } = fixture({ existing: ["motion-engine-premiere-probe.prproj"] });
  ppro.Project.createProject = () => { throw new Error("must not create"); };
  await assert.rejects(runProbe(ppro, fs), /already exists/i);
});

test("does not report PASS if marker is missing after reopen", async () => {
  const { fs, ppro, destination } = fixture({ loseMarker: true });
  await assert.rejects(runProbe(ppro, fs), /marker was lost/i);
  assert.equal(destination.report, undefined);
});
