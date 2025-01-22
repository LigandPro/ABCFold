// https://stackoverflow.com/a/73891404
async function replaceAsync(string, regexp, replacerFunction) {
    const replacements = await Promise.all(
        Array.from(string.matchAll(regexp), replacerFunction));
    let i = 0;

    return string.replace(regexp, () => replacements[i++]);
}


function compileTemplate(template) {
    return replaceAsync(template, /\{\{(\S+)}}/g, async match => {
            const value = match[1];

            if (value.startsWith('@')) {
                return Promise.resolve(`../src/${value.slice(1)}`);
            } else {
                return await fetch(`../src/templates/${value}`)
                    .then(response => response.text())
                    .then(template => {
                        return compileTemplate(template);
                    });
            }
        }
    );
}

const main = document.querySelector('main');

compileTemplate(main.innerHTML).then((result) => {
    main.innerHTML = result;

    const uploadTab = main.querySelector('button[data-bs-target="#upload"]'); //.classList.add('active');
    // new bootstrap.Tab(uploadTab).show();

    main.querySelector('button[data-bs-target="#examples"]').parentElement.remove();
    // main.querySelector('button[data-bs-target="#upload"]').parentElement.remove();
    // main.querySelector('button[data-bs-target="#Offline version"]').parentElement.remove();
    // main.querySelector('button[data-bs-target="#Citation"]').parentElement.remove();

    import('./pae-viewer-standalone.js');
});
