---
title: About
---

# About

The Psion Software Index is an attempt to index all the software written for the Psion range of palmtop computers. It is currently primarily focused on EPOC software which includes the Series 5, Series 5mx, Revo, Series 7 and netbook machines, but it also includes some software for the SIBO platform, targeting the Series 3, 3a, 3c, Siena, and 3mx, with more support to be added over time.

The index is created by extracting metadata from Psion programs that have been preserved on the [Internet Archive](https://archive.org) (see <a href="{{ "/sources" | absolute_url }}">Sources</a>). The hope is to augment this with manually curated data including descriptions, categorization, and screenshots.

The current version comprises a static HTML file (which you see here) but the plan is to publish JSON versions of the index to make it easy to build tools for searching the index, viewing entries, and downloading resources based on the references to the original source material. It would be great to have an app store on the Psion someday!

The index is built by [Jason Morley](https://jbmorley.co.uk), and [Tom Sutcliffe](https://github.com/tomsci), with gentle encouragement from Alex Brown and the [Psion Discord](https://discord.gg/8ZkKKkA), and includes software from the [OpoLua](https://opolua.org) OPL on iOS project.

## Summary

<table class="statistics">
    <tr>
        <td class="stat">{{ site.data.summary.installerCount }}</td>
        <td>Programs and installers</td>
    </tr>
    <tr>
        <td class="stat">{{ site.data.summary.uidCount }}</td>
        <td>Unique programs (by UID)</td>
    </tr>
    <tr>
        <td class="stat">{{ site.data.summary.versionCount }}</td>
        <td>Unique versions</td>
    </tr>
    <tr>
        <td class="stat">{{ site.data.summary.shaCount }}</td>
        <td>Unique files</td>
    </tr>
    <tr>
        <td class="stat">{{ site.data.sources.size }}</td>
        <td>Sources</td>
    </tr>
</table>

## Sources

The index is built from the following Internet Archive sources:

{% for source in site.data.sources %}<details>
    <summary>{% if source.html_url %}<a href="{{ source.html_url }}">{% endif %}{% if source.name %}{{ source.name }}{% else %}{{ source.path }}{% endif %}{% if source.html_url %}</a>{% endif %}</summary>
    <div class="source-description">{{ source.description | strip_html }}</div>
</details>{% endfor %}
