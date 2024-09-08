# conda-forge-feedstock-ops

a docker image to run containerized feedstock operations

## Description

This image contains the code and integrations to run containerized feedstock operations
via the [conda-forge-feedstock-ops](https://github.com/conda-forge/conda-forge-feedstock-ops) Python package.

## License

This image is licensed under [BSD-3 Clause](https://github.com/conda-forge/conda-forge-feedstock-ops/blob/main/LICENSE).

## Documentation & Contributing

You can find documentation for how to use the image on the
upstream [repo](https://github.com/conda-forge/conda-forge-feedstock-ops) and in the sections below.

To get in touch with the maintainers of this image, please
[make an issue](https://github.com/conda-forge/conda-forge-feedstock-ops/issues/new/choose)
and bump the `@conda-forge/core` team.

Contributions are welcome in accordance
with conda-forge's [code of conduct](https://conda-forge.org/community/code-of-conduct/). We accept them through pull requests on the
upstream [repo](https://github.com/conda-forge/conda-forge-feedstock-ops/compare).

## Important Image Tags

- latest: the image built from the latest tagged release of the package
- `semver`: the image built from the tagged release of the package with the corresponding version

*Every tag of the upstream package will have a corresponding tag for this image.*
*Each tagged release uses the corresponding tagged image by default.*

## Getting Started & Usage

To use this image, you should run it through the corresponding Python package.

First, install the package:

```bash
conda install -c conda-forge conda-forge-feedstock-ops
```

Then for your feedstock, you can call commands like this:

```python
from conda_forge_feedstock_ops.rerender import rerender

commit_msg = rerender(path_to_feedstock)
```
