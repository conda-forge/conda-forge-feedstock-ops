FROM mambaorg/micromamba:2.6.2
# ARG SETUPTOOLS_SCM_PRETEND_VERSION
# ENV SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION} \

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


# FROM quay.io/condaforge/linux-anvil-cos7-x86_64:latest

# # baseline env
# ENV TMPDIR=/tmp
# ENV CF_FEEDSTOCK_OPS_DIR=/opt/cf-feedstock-ops
# ENV CF_FEEDSTOCK_OPS_ENV=cf-feedstock-ops

# # use bash for a while to make conda manipulations easier
# SHELL ["/bin/bash", "-l", "-c"]

# # build the conda env first
# COPY environment.yml $CF_FEEDSTOCK_OPS_DIR/environment.yml
# RUN conda activate base && \
#     conda env create -f $CF_FEEDSTOCK_OPS_DIR/environment.yml -n $CF_FEEDSTOCK_OPS_ENV && \
#     conda clean --all --yes && \
#     # Lucky group gets permission to write in the conda dir
#     chown -R root /opt/conda && \
#     chgrp -R lucky /opt/conda && chmod -R g=u /opt/conda && \
#     conda deactivate

# # deal with entrypoint
# COPY entrypoint /opt/docker/bin/
# RUN chmod +x /opt/docker/bin/entrypoint

# # now install the bot code
# COPY . $CF_FEEDSTOCK_OPS_DIR
# RUN conda activate base && \
#     conda activate $CF_FEEDSTOCK_OPS_ENV && \
#     cd $CF_FEEDSTOCK_OPS_DIR && \
#     pip install --no-deps --no-build-isolation -e . && \
#     cd - && \
#     conda deactivate && \
#     conda deactivate

# # now make the conda user for running tasks and set the user
# RUN useradd --shell /bin/bash -c "" -m conda
# ENV HOME=/home/conda
# ENV USER=conda
# ENV LOGNAME=conda
# ENV MAIL=/var/spool/mail/conda
# ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/conda/bin
# # make symlink - actually directory gets made at run time in the entrypoint
# RUN ln -s ${TMPDIR}/conda_user_conda_build_locks $HOME/.conda_build_locks
# RUN chown conda:conda $HOME && \
#     cp -R /etc/skel $HOME && \
#     chown -R conda:conda $HOME/skel && \
#     (ls -A1 $HOME/skel | xargs -I {} mv -n $HOME/skel/{} $HOME) && \
#     rm -Rf $HOME/skel && \
#     cd $HOME
# USER conda

# # deal with git config for user and mounted directory
# RUN conda activate $CF_FEEDSTOCK_OPS_ENV && \
#     git config --global --add safe.directory /cf_feedstock_ops_dir && \
#     git config --global init.defaultBranch main && \
#     git config --global user.email "conda@conda.conda" && \
#     git config --global user.name "conda conda" && \
#     conda deactivate && \
#     conda init --all --user

# # put the shell back
# SHELL ["/bin/sh", "-c"]
