module Redirects
  class ProgramPageGenerator < Jekyll::Generator
    safe true

    def generate(site)
      site.data['redirects'].each do |redirect|
        site.pages << Redirect.new(site, redirect)
      end
    end
  end

  # Subclass of `Jekyll::Page` with custom method definitions.
  class Redirect < Jekyll::Page
    def initialize(site, redirect)
      @site = site             # the current site instance.
      @base = site.source      # path to the source directory.
      @dir  = redirect['path']  # the directory the page will reside in.

      # All pages have the same filename, so define attributes straight away.
      @basename = 'index'      # filename without the extension.
      @ext      = '.html'      # the extension.
      @name     = 'index.html' # basically @basename + @ext.

      # Initialize data hash with a key pointing to all posts under current category.
      # This allows accessing the list in a template via `page.linked_docs`.
      @data = {
        'linked_docs' => redirect,
        'layout' => 'redirect',
        'redirect' => redirect,
      }

      @redirect = redirect
      @content = ""

      # Look up front matter defaults scoped to type `categories`, if given key
      # doesn't exist in the `data` hash.
      data.default_proc = proc do |_, key|
        site.frontmatter_defaults.find(relative_path, :categories, key)
      end
    end

    # Placeholders that are used in constructing page URL.
    def url_placeholders
      {
        :path       => @dir,
        :category   => @dir,
        :basename   => basename,
        :output_ext => output_ext,
      }
    end
  end
end
