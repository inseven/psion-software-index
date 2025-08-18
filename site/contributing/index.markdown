---
title: Contributing
---

# Contributing

We're excited for all contributions to to the Software Index!

## Content

The index is built from content uploaded to the [Internet Archive](https://archive.org). If you have a suggestion for an item we should add, please [raise a GitHub issue][github-new-issue], [send an email](mailto:support@jbmorley.co.uk), or [propose a change](https://github.com/inseven/psion-software-index/blob/main/libraries/full.yaml).

We're also starting to explore adding content from live websites, and Wayback Machine archives. If you have suggestions for this type of content, please [raise a GitHub issue][github-new-issue] or [send an email](mailto:support@jbmorley.co.uk).

If you have archives of Psion software that aren't already on the Internet archive, please consider [uploading them](https://archive.org/create/). ❤️

## Screenshots and Metadata

The Software Index incorporates manually created content, stored in the '[overlays](https://github.com/inseven/psion-software-index/tree/main/overlays)' directory. We would love help generating this content; please consider raising a PR, or [getting in touch](mailto:support@jbmorley.co.uk).

Program-specific content is grouped into a folder named with the program's UID[^uid]. For example, the current overlay directory structure looks like this:

- overlays
  - 0x02000006
    - screenshot.png
  - ...
  - 0x100053f0 NEUON PacMan
    - 1-pacman.png
    - 2-spash-screen.png
    - 3-about-screen.png
    - 4-hiscore-table.png
    - 5-preferences.png
    - index.md
  - 0x101f438f
    - game.png
    - splash.png

[^uid]: You can find program UIDs under the title of program-specific pages in the index. They are an 8-digit hexadecimal number, beginning `0x`.

> [!NOTE]
> The indexer will ignore all text after a space in the top-level folder names allowing you to add comments, as seen in the 'PacMan' folder above.

### Screenshots

All images in a program's overlay directory will automatically be treated as screenshots and are alphabetically ordered by filename.

### Metadata

Metadata is stored in 'index.md' Markdown files with Frontmatter, and is limited to specific known keys.

For example, the metadata for [PacMan](/programs/0x100053f0/) is as follows:

```text
---
subtitle: PacMan clone
category: games/arcade
publishers:
- Neuon
authors:
- Jérôme Dern
developer_url: https://neuon.com
---

Published by Neuon, PacMan is a clone. It's let down a little by EPOC’s redraw and animation speed, and the difficulty ramps quite unexpectedly.
```

Supported metadata fields are as follows:

- `subtitle` - string
- `category` - string enum, one of
  - `connectivity/web`
  - `connectivity/other`
  - `games/action`
  - `games/adventure`
  - `games/arcade`
  - `games/board`
  - `games/puzzle`
  - `games/racing`
  - `games/rpg`
  - `games/shooter`
  - `games/simulation`
  - `games/sports`
  - `games/strategy`
  - `games/other`
  - `multimedia/ebooks`
  - `multimedia/music`
  - `multimedia/photo`
  - `multimedia/video`
  - `multimedia/other`
  - `productivity/calculators`
  - `productivity/date-and-time`
  - `productivity/graphics`
  - `productivity/office`
  - `productivity/organizers`
  - `productivity/scientific`
  - `productivity/other`
  - `system/addons`
  - `system/file-management`
  - `system/input`
  - `system/utilities`
  - `system/other`
  - `desktop/other`
- `publishers` - array of strings
- `authors` - array of strings
- `developer_url` - string

All fields are optional.

[github-new-issue]: https://github.com/jbmorley/psion-software-index/issues/new?title=Content%20Proposal&labels=content
