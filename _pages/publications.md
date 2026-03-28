---
layout: archive
title: "Publications"
permalink: /publications/
author_profile: true
---

{% include base_path %}

<div class="intro-highlight" markdown="1">
You can also find the full list on my [Google Scholar profile](https://scholar.google.com/citations?user=D2X7Qv0AAAAJ&hl=en){:target="_blank"} — auto-updated via GitHub Actions.
</div>

<div class="pub-list">
{% assign pubs_by_year = site.publications | sort: "date" | reverse | group_by_exp: "pub", "pub.date | date: '%Y'" %}
{% for year_group in pubs_by_year %}
<h2 class="archive__subtitle">{{ year_group.name }}</h2>
{% for post in year_group.items %}
  {% include archive-single.html %}
{% endfor %}
{% endfor %}
</div>

<p style="margin-top:2em; font-size:.85em; color:#8a9cc0;"><sup>*</sup> Equal authorship</p>
