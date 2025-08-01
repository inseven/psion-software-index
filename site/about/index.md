---
title: About
---

# About

The Psion Software Index is an attempt to index all the software written for the Psion range of palmtop computers. It is currently primarily focused on EPOC software which includes the Series 5, Series 5mx, Revo, Series 7 and netbook machines, but it also includes some software for the SIBO platform, targeting the Series 3, 3a, 3c, Siena, and 3mx, with more support to be added over time.

The index is created by extracting metadata from Psion programs that have been preserved on the [Internet Archive](https://archive.org) and other sources (see <a href="{{ "/sources" | absolute_url }}">Sources</a>). It is augmented with manually curated data including descriptions, categorization, and screenshots.

The index is built by [Jason Morley](https://jbmorley.co.uk), and [Tom Sutcliffe](https://github.com/tomsci), with gentle encouragement from Alex Brown and the [Psion Discord](https://discord.gg/8ZkKKkA), and use software from the [OpoLua](https://opolua.org) project for indexing.

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

The index is built from the following sources:

{% assign sources = site.data.sources | sort: "name" %}
<ul>
{% for source in sources %}
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
