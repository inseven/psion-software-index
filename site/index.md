---
title: Library
layout: full
---

# Psion Software Index

<div class="search-header">
    <input type="text" id="search" name="search" class="search" placeholder="Filter" />
</div>

<ul id="applications" class="applications"></ul>

<script type="module">
    const applicationsList = document.getElementById("applications");
    const searchInput = document.getElementById("search");
    const response = await fetch("/api/v1/groups");
    const groups = await response.json();
    var filteredGroups = groups;
    let index = 0;

    function appendGroup(group) {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = "/programs/" + group.uid;
        const icon = document.createElement("img");
        icon.classList.add("icon");
        if (!!group.icon) {
            icon.src = group.icon.path;
            icon.width = group.icon.width;
            icon.height = group.icon.height;
        } else {
            icon.src = "/images/unknown.gif"
            icon.width = 48;
            icon.height = 48;
        }
        a.appendChild(icon);
        const name = document.createElement("span");
        name.textContent = group.name;
        a.appendChild(name);
        li.appendChild(a);
        applicationsList.appendChild(li);
    }

    function filter(text) {
        index = 0;
        text = text.toLowerCase();
        applicationsList.innerHTML = "";
        filteredGroups = groups.filter(function(group) {
            return group.name.toLowerCase().includes(text);
        });
        update();
    }

    function update() {
        const threshold = window.innerHeight * 2;
        console.log("Loading...");
        while (index < filteredGroups.length && document.body.scrollHeight <= window.innerHeight + window.scrollY + threshold) {
            const group = filteredGroups[index];
            appendGroup(group);
            index = index + 1;
        }
    }

    function debounce(fn, delay) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => fn(...args), delay);
        };
    }

    searchInput.addEventListener('input', debounce(function(event) {
        filter(searchInput.value);
    }, 30));

    window.addEventListener('scroll', debounce(update, 100));
    window.addEventListener('resize', debounce(update, 100));
    update();
</script>
