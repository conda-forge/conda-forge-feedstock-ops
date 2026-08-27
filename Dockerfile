FROM mambaorg/micromamba:2.9.0

# baseline env
ENV TMPDIR=/tmp \
    CF_FEEDSTOCK_OPS_DIR=/opt/cf-feedstock-ops \
    CF_FEEDSTOCK_OPS_ENV=cf-feedstock-ops

COPY --chown=$MAMBA_USER:$MAMBA_USER . $CF_FEEDSTOCK_OPS_DIR
RUN micromamba install --name base --yes --file $CF_FEEDSTOCK_OPS_DIR/environment.yml && \
    # make symlink for conda-build locks (actual directory gets made at run time in the entrypoint)
    # see https://github.com/conda-forge/conda-forge-feedstock-ops/pull/59
    ln -s $TMPDIR/conda_user_conda_build_locks $HOME/.conda_build_locks && \
    # deal with entrypoint
    chmod +x $CF_FEEDSTOCK_OPS_DIR/entrypoint && \
    # this eval is needed to run activate, but won't be needed later
    eval "$(micromamba shell hook --shell bash)" && \
    micromamba activate base && \
    # remove some testing deps
    # install package
    cd $CF_FEEDSTOCK_OPS_DIR && \
    pip install --no-deps --no-build-isolation -e . && \
    cd - && \
    # deal with git config
    git config --global --add safe.directory /cf_feedstock_ops_dir && \
    git config --global init.defaultBranch main && \
    git config --global user.email "mambauser@mambauser.mambauser" && \
    git config --global user.name "mambauser mambauser" && \
    micromamba deactivate && \
    # clean out data we do not need
    micromamba clean --all --yes && \
    rm -rf $CF_FEEDSTOCK_OPS_DIR/.git  && \
    find ${MAMBA_ROOT_PREFIX} -follow -type f -name '*.a' -delete && \
    find ${MAMBA_ROOT_PREFIX} -follow -type f -name '*.pyc' -delete

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "/opt/cf-feedstock-ops/entrypoint"]
