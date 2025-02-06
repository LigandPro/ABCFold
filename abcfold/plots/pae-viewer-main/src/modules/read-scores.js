function isNumber(value) {
    return typeof value === 'number' && !isNaN(value);
}

export function readScores(file) {
    const reader = new FileReader();

    const promise = new Promise((resolve, reject) => {
        reader.addEventListener('load', () => {
            let data = null;

            try {
                data = JSON.parse(reader.result);
            } catch (error) {
                reject({
                    type: 'scores-input-error',
                    message: "The JSON file couldn't be parsed correctly!",
                });
                return;
            }

            if (Array.isArray(data)) {
                if (data.length === 0) {
                    reject({
                        type: 'scores-input-error',
                        message: "The JSON file was empty!",
                    });
                    return;
                }

                data = data[0];
            }

            if (
                data === null || typeof data !== 'object' || Array.isArray(data)
            ) {
                reject({
                    type: 'scores-input-error',
                    message: "The JSON file must contain either an object or"
                        + " an array where the first element is an object!",
                });
                return;
            }

            data = new Map(Object.entries(data));

            let maxPae = data.get('max_pae')
                ?? data.get('max_predicted_aligned_error');

            if (maxPae !== undefined) {
                if (!isNumber(maxPae) || maxPae <= 0) {
                    reject({
                        type: 'scores-input-error',
                        message: `The maximum PAE must be a number > 0, was`
                            + ` '${JSON.stringify(maxPae)}'!`,
                    });
                    return;
                }
            }

            const pae = data.get('pae') ?? data.get('predicted_aligned_error');
            let length = 0;

            if (pae === undefined) {
                reject({
                    type: 'scores-input-error',
                    message: "The JSON file must contain a key 'pae' or"
                        + " 'predicted_aligned_error'!",
                });
                return;
            }

            if (!Array.isArray(pae)) {
                reject({
                    type: 'scores-input-error',
                    message: "The PAE value must be an N*N array of"
                        + " numbers!",
                });
                return;
            }

            length = pae.length;

            if (length === 0) {
                reject({
                    type: 'scores-input-error',
                    message: "The PAE array can't be empty!",
                });
                return;
            }

            let foundMax = 0;

            for (const [rowIndex, row ]of pae.entries()) {
                if (!Array.isArray(row)) {
                    reject({
                        type: 'scores-input-error',
                        message: `The PAE value must be an N*N array of`
                            + ` numbers! However, row ${rowIndex} is not an`
                            + ` array!`,
                    });
                    return;
                }

                if (row.length !== length) {
                    reject({
                        type: 'scores-input-error',
                        message: `The PAE value must be an N*N array of`
                            + ` numbers! However, the number of columns`
                            + ` (${row.length}) in row ${rowIndex} does`
                            + ` not match number of rows (${length})!`,
                    });
                    return;
                }

                for (const [columnIndex, value] of row.entries()) {
                    if (!isNumber(value) || value < 0) {
                        reject({
                            type: 'scores-input-error',
                            message: `The PAE values must be numbers >= 0,`
                                + ` but column ${columnIndex} in row`
                                + ` ${rowIndex} contained`
                                + ` '${JSON.stringify(value)}'!`,
                        });
                        return;
                    }

                    if (value > foundMax) {
                        foundMax = value;
                    }
                }
            }

            let overwrittenMax = null;

            if (maxPae === undefined) {
                maxPae = foundMax;
            } else if (foundMax > maxPae) {
                overwrittenMax = maxPae;
                maxPae = foundMax;
            }

            const mean = array => array.reduce((a, b) => a + b) / array.length;

            const plddt = data.get('plddt');

            let meanPlddt = null;

            if (plddt === undefined) {
                meanPlddt = null;
            } else {
                if (!Array.isArray(plddt) ) {
                    reject({
                        type: 'scores-input-error',
                        message: "The pLDDT value must be an array of numbers"
                            + " with the number of residues as length!",
                    });
                    return;
                } else if (plddt.length !== length) {
                    reject({
                        type: 'scores-input-error',
                        message: `Length of pLDDT array (${plddt.length})`
                            + ` didn't match length of PAE array (${length})!`,
                    });
                   return;
                } else {
                    for (const [columnIndex, value] of plddt.entries()) {
                        if (!isNumber(value) || value < 0 || value > 100) {
                            reject({
                                type: 'scores-input-error',
                                message: `The pLDDT values must be numbers`
                                    + ` between 0 and 100, but column`
                                    + ` ${columnIndex} contained`
                                    + ` '${JSON.stringify(value)}'!`,
                            });
                            return;
                        }
                    }
                }

                meanPlddt = mean(data.get('plddt')).toFixed(4);
            }

            let ptm = data.get('ptm');

            if (ptm === undefined) {
                ptm = null;
            } else {
                if (!isNumber(ptm) || ptm < 0 || ptm > 1) {
                    reject({
                        type: 'scores-input-error',
                        message: `The pTM must be a number in (0,1], but was `
                            + ` '${JSON.stringify(ptm)}'!`,
                    });
                    return;
                }

                ptm = ptm.toFixed(4);
            }

            let iptm = data.get('iptm');

            if (iptm === undefined) {
                iptm = null;
            } else {
                if (!isNumber(iptm) || iptm < 0 || iptm > 1) {
                    reject({
                        type: 'scores-input-error',
                        message: `The ipTM must be a number in (0,1], but was `
                            + ` '${JSON.stringify(iptm)}'!`,
                    });
                    return;
                }

                iptm = iptm.toFixed(4);
            }

            resolve({
                pae: pae,
                maxPae: maxPae,
                plddt: meanPlddt,
                ptm: ptm,
                iptm: iptm,
                overwrittenMax: overwrittenMax,
            });
        }, false);

        reader.addEventListener('error', () => {
            reject({
                type: 'scores-input-error',
                message: "The JSON file couldn't be read correctly!",
            });
        });
    });

    reader.readAsText(file);
    return promise;
}
