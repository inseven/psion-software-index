---
title: Library
layout: full
---

# Psion Software Index

<div class="search-header">
    <form id="search-form" class="search-form">
        <input type="text" id="search" name="search" class="search" placeholder="Filter" autocorrect="off" />
        <button type="reset" class="clear"><picture><source srcset="/images/x-dark.svg" media="(prefers-color-scheme: dark)" /><img src="/images/x-light.svg" /></picture></button>
    </form>
</div>

<ul id="applications" class="applications"></ul>

<script type="module">
    const applicationsList = document.getElementById("applications");
    const searchForm = document.getElementById("search-form");
    const searchInput = document.getElementById("search");
    const response = await fetch("/api/v1/groups");
    const groups = await response.json();
    var filteredGroups = groups;
    let index = 0;

    function appendGroup(group) {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = "/programs/" + group.id;
        const iconContainer = document.createElement("div");
        iconContainer.classList.add("icon-wrapper");
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
        iconContainer.appendChild(icon);
        a.appendChild(iconContainer);
        const label = document.createElement("div");
        label.classList.add("label");
        const name = document.createElement("div");
        name.classList.add("program-name");
        name.textContent = group.name;
        label.appendChild(name);
        const platformElement = document.createElement("ul");
        platformElement.classList.add("program-platforms")
        for (const platform of group.platforms) {
            const platformItem = document.createElement("li");
            platformItem.textContent = platform;
            platformElement.append(platformItem);
        }
        label.appendChild(platformElement);
        a.appendChild(label);
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

    searchForm.addEventListener('reset', function(event) {
        filter("");
        searchInput.focus();
    });
    searchInput.addEventListener('input', debounce(function(event) {
        filter(searchInput.value);
    }, 30));

    window.addEventListener('scroll', debounce(update, 100));
    window.addEventListener('resize', debounce(update, 100));
    update();
</script>
