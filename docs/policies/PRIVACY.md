# Privacy policy

MLC Player is a local desktop media player. It has no user account system and
does not operate an MLC Player data-collection server.

## No telemetry or analytics

MLC Player does not include advertising, telemetry, analytics, crash-report
uploading or usage profiling. Settings, recent-file entries and application
logs remain on the computer under `%APPDATA%\MLCPlayer`. They are not
automatically uploaded by the application. A user may inspect or delete logs
from `Tools -> Log Management`.

Normal internet infrastructure can still observe standard connection data
such as the public IP address, time and requested host when one of the network
features below is used.

## Automatic update check

At startup the application makes a read-only HTTPS request to:

`https://api.github.com/repos/IzzmooPro/MLCPlayer/releases/latest`

This retrieves public release metadata. It does not intentionally send media
names, local paths, recent files, settings or log contents. If the user starts
an update, the selected installer and its detached signature are downloaded
from the corresponding public GitHub Release.

## User-requested network activity

- **URL playback:** When the user chooses URL playback, the address is passed
  to libmpv. Website extraction additionally uses the optional bundled yt-dlp
  and Deno components. Those tools contact the address and services required
  by the selected website. Their behavior and the website's privacy policy
  apply to that request.
- **Manual GitHub links:** The application opens the public MLC Player GitHub
  page in the default browser only after the user selects the corresponding
  action.
- **OpenSubtitles:** Source code for OpenSubtitles integration exists, but its
  user interface is disabled while public desktop distribution terms are
  being reviewed. Normal users cannot start an OpenSubtitles search in the
  current release.

Local media playback does not require an MLC Player account or an MLC Player
network service.

## Installation and removal

The installer requests Windows administrator approval and clearly identifies
the program being installed. The main player and optional Internet Video
add-on have separate uninstallers. Uninstallation deliberately keeps settings
and logs so an update or reinstall does not erase user preferences; the user
may delete `%APPDATA%\MLCPlayer` manually if complete local-data removal is
desired.

## Changes

Network behavior added in a future version must be documented here before the
release is eligible for code signing. The policy revision is tracked in the
public source repository.
