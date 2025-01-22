export function readChains(file, labels) {
    return (new NGL.Stage()).loadFile(
        file, {name: 'structure'}
    ).catch(error => {
        let message = `Couldn't read file '${file.name}'!`;

        if (file?.name && file.name.slice(-3).toLowerCase() === 'cif') {
            message += " If you're using the PDBx/mmCIF file format, please"
                + " note that the NGL Viewer support for this format is"
                + " unfortunately unstable and might fail.";
        }

        throw {
            type: 'structure-input-error',
            message: message,
            file: file,
            cause: error,
        };
    }).then(component => {
        const chains = [];
        let offset = 0;

        component.structure.eachChain(chain => {
            const sequence = [];
            const residueProxy = chain.structure.getResidueProxy(chain.residueOffset);

            if (residueProxy.isPolymer()) {
                chain.eachResidue(r => {
                    let code;

                    if (r.isProtein()) {
                        code = r.getResname1();
                    } else if (r.isDna()) {
                        code = r.resname[1];
                    } else {  // RNA
                        code = r.resname[0];
                    }

                    sequence.push(code);
                });
            } else {
                chain.eachAtom(a => {
                    sequence.push(a.atomname[0]);
                });
            }

            let type;

            if (residueProxy.isProtein()) {
                type = 'protein';
            } else if (residueProxy.isDna() || residueProxy.isRna()) {
                type = 'nucleotide';
            } else {
                type = 'molecule';
            }

            chains.push({
                chain: chain.chainname,
                length: sequence.length,
                sequence: sequence,
                offset: offset,
                type: type
            });

            offset += sequence.length;
        });

        if (labels === null) {
            labels = chains.map(chain => chain.chain);
        } else if (labels.length !== chains.length) {
            throw {
                type: 'invalid-chain-labels',
                message: `The number of labels (${labels.length}) doesn't`
                    + ` match the number of chains in the structure`
                    + ` (${chains.length})!`,
                labelsLength: labels.length,
                chainsLength: chains.length
            };
        }

        return chains.map((chain, i) => ({
            ...chain,
            id: labels[i],
            title: labels[i],
            uniprot: labels[i],
            index: i,
            position: i,
        }));
    });
}
