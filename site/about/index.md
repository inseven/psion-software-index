---
title: About
---

# About

The Psion Software Index is an attempt to index all the software written for the Psion range of palmtop computers. It is currently primarily focused on EPOC software which includes the Series 5, Series 5mx, Revo, Series 7 and netbook machines, but it also includes some software for the SIBO platform, targeting the Series 3, 3a, 3c, Siena, and 3mx, with more support to be added over time.

The index is created by extracting metadata from Psion programs that have been preserved on the [Internet Archive](https://archive.org) and other sources. It is augmented with manually curated data including descriptions, categorization, and screenshots.

## Authors

- [Jason Morley](https://jbmorley.co.uk)
- [Tom Sutcliffe](https://github.com/tomsci)

## Contributors

- scienceapps

## License

### Source Code

Source code used to generate the Psion Software Index is licensed under the MIT License (see [LICENSE](https://github.com/inseven/psion-software-index/blob/main/LICENSE)). It depends on the following separately licensed third-party libraries and components:

- [Feather](https://feathericons.com), MIT License
- [jekyll-humanize](https://github.com/23maverick23/jekyll-humanize), MIT License
- [OpoLua](https://github.com/inseven/opolua), MIT License

### Content

The Psion Software Index is automatically generated from publicly accessible sources (primarily the Internet Archive; see below). Programs, installers, and other files included in the Index remain the sole copyright of their original authors and publishers.

The Index has been created as a good faith preservation effort, and a way to support people who wish to continue using Psion and Psion-compatible devices.

> [!IMPORTANT]
> If you are the current copyright holder of content presented within the Index and wish your content removed or, if you are a website author and wish your site excluded from the Index, please [reach out by email](mailto:support@jbmorley.co.uk).

## Summary

### Programs---{{ site.data.summary.programs.epoc16 | plus: site.data.summary.programs.epoc32 }}

_Top level grouping of releases of different versions and variants, corresponding with the history of a single application or game (e.g., PacMan, released by NEUON)._

- EPOC16---{{ site.data.summary.programs.epoc16 }}
- EPOC32---{{ site.data.summary.programs.epoc32 }}

```mermaid
pie
    "EPOC16" : {{ site.data.summary.programs.epoc16 }}
    "EPOC32" : {{ site.data.summary.programs.epoc32 }}
```

### Releases---{{ site.data.summary.releases.unique.epoc16 | plus: site.data.summary.releases.unique.epoc32 }}

_Individual instances of an installable program; either a .app, .opa, or .sis. Releases are uniqued by a hash of their file contents._

- EPOC16---{{ site.data.summary.releases.unique.epoc16 }}
- EPOC32---{{ site.data.summary.releases.unique.epoc32 }}

```mermaid
pie
    "EPOC16" : {{ site.data.summary.releases.unique.epoc16 }}
    "EPOC32" : {{ site.data.summary.releases.unique.epoc32 }}
```

### Size---{{ site.data.summary.size.unique.epoc16 | plus: site.data.summary.size.unique.epoc32 | filesize }}

- EPOC16---{{ site.data.summary.size.unique.epoc16 | filesize }}
- EPOC32---{{ site.data.summary.size.unique.epoc32 | filesize }}

```mermaid
pie
    "EPOC16" : {{ site.data.summary.size.unique.epoc16 }}
    "EPOC32" : {{ site.data.summary.size.unique.epoc32 }}
```

### Sources---{{ site.data.summary.sources }}

#### Internet Archive

{% assign internet_archive_sources = site.data.sources | where: "kind", "internet-archive" | sort: "name" %}

{% for source in internet_archive_sources %}
{% if source.description %}
<details>
    <summary>{% if source.html_url %}<a href="{{ source.html_url }}">{% endif %}{% if source.name %}{{ source.name }}{% else %}{{ source.path }}{% endif %}{% if source.html_url %}</a>{% endif %}</summary>
    <div class="source-description">{{ source.description | strip_html }}</div>
</details>
{% else %}
{% if source.html_url %}<a href="{{ source.html_url }}">{% endif %}{% if source.name %}{{ source.name }}{% else %}{{ source.path }}{% endif %}{% if source.html_url %}</a>{% endif %}
{% endif %}
{% endfor %}

{% assign snapshot_sources = site.data.sources | where: "kind", "snapshot" | sort: "name" %}

{% if snapshot_sources.size > 0 %}

#### Websites

<ul>
{% for source in snapshot_sources %}
<li>
{% if source.description %}
<details>
    <summary>{% if source.html_url %}<a href="{{ source.html_url }}">{% endif %}{% if source.name %}{{ source.name }}{% else %}{{ source.path }}{% endif %}{% if source.html_url %}</a>{% endif %}</summary>
    <div class="source-description">{{ source.description | strip_html }}</div>
</details>
{% else %}
{% if source.html_url %}<a href="{{ source.html_url }}">{% endif %}{% if source.name %}{{ source.name }}{% else %}{{ source.path }}{% endif %}{% if source.html_url %}</a>{% endif %}
{% endif %}
</li>
{% endfor %}
</ul>

{% endif %}
