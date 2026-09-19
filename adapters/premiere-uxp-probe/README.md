# Premiere 2026 UXP compatibility probe

This is a narrow native test, not the MotionSpec-to-Premiere adapter. It uses a public synthetic PNG to create one new project with one 30 fps sequence and one comment marker. It then saves, closes, reopens, and reads back the frame rate, video track, marker, and media link. A `PASS` report is written only after every check succeeds.

## Requirements

- Licensed Premiere Pro 26.3 or newer. The first tested host is intended to be 26.5.1 on Windows.
- Adobe UXP Developer Tool (UDT) 2.2 or newer, installed through Creative Cloud Desktop.
- On Windows, Premiere **Edit > Preferences > Plugins > Enable developer mode**, followed by a Premiere restart. This setting is for loading a local development plugin; the user must enable it in Premiere.

## Run

1. Open UDT and choose **Add Plugin**. Select this folder's `manifest.json`.
2. Load the plugin into Premiere. In Premiere choose **Window > UXP Plugins > Motion Engine Premiere Probe > Create and verify sample project**.
3. Select an empty scratch folder. The command refuses to replace a previous probe project or report.
4. Check `motion-engine-premiere-probe-report.json` in that folder. `status: PASS` means that the saved project reopened with one linked video clip and a marker at one second. The project remains open so you can inspect it.
5. If there is no report, open the UDT console for the precise failure. The project may exist but must be treated as unverified.

The sample image is linked to this plugin folder. Keep the folder in place until inspection finishes. This probe does not test portable packaging, text editability, audio, cuts, sequence profile fidelity, or video export. Those remain separate adapter gates.

The API calls follow Adobe's [Project](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/project), [Markers](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/markers), [VideoTrack](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/videotrack), and [plugin development](https://developer.adobe.com/premiere-pro/uxp/introduction/essentials/dev-tools/) documentation.
