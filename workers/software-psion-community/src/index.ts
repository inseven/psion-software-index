// Copyright (c) 2026 Jason Morley
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

import { env } from "cloudflare:workers";

export default {
    async fetch(req) {

        // Only allow GET and HEAD requests.
        if (req.method !== "GET" && req.method !== "HEAD") {
            return new Response("Method not allowed", { status: 405, headers: { allow: "GET, HEAD" } });
        }

        // Get the path details.
        let path: string;
        try {
            path = decodeURIComponent(new URL(req.url).pathname).slice(1);
        } catch {
            return new Response("Bad request", { status: 400 });
        }
        const isDirectory = path === "" || path.endsWith("/");
        const name = path.slice(path.lastIndexOf("/") + 1);

        // Fix-up directory paths.
        const index = path.startsWith("api/v1/") ? "index.json" : "index.html";
        const key = isDirectory ? `${path}${index}` : path;

        // Return the object if it exists.
        const obj = await env.BUCKET.get(key);
        if (obj) {
            const headers = new Headers();
            obj.writeHttpMetadata(headers);
            headers.set("etag", obj.httpEtag);
            return new Response(req.method === "HEAD" ? null : obj.body, { headers });
        }

        // If we weren't able to find an object and didn't see directory or file markers, we assume the user entered a
        // bare directory name without a trailing slash and redirect.
        if (!isDirectory) {
            const url = new URL(req.url);
            url.pathname += "/";
            return Response.redirect(url.toString(), 302);
        }

        // Finally, we give up.
        return new Response("Not found", { status: 404 });
    },
} satisfies ExportedHandler;
