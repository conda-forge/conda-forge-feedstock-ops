FROM quay.io/condaforge/linux-anvil-cos7-x86_64:latest

# baseline env
ENV TMPDIR=/tmp
ENV CF_FEEDSTOCK_OPS_DIR=/opt/cf-feedstock-ops
ENV CF_FEEDSTOCK_OPS_ENV=cf-feedstock-ops

# use bash for a while to make conda manipulations easier
SHELL ["/bin/bash", "-l", "-c"]

# build the conda env first
COPY environment.yml $CF_FEEDSTOCK_OPS_DIR/environment.yml
RUN conda activate base && \
    conda env create -f $CF_FEEDSTOCK_OPS_DIR/environment.yml -n $CF_FEEDSTOCK_OPS_ENV && \
    conda clean --all --yes && \
    # Lucky group gets permission to write in the conda dir
    chown -R root /opt/conda && \
    chgrp -R lucky /opt/conda && chmod -R g=u /opt/conda && \
    conda deactivate

# deal with entrypoint
COPY entrypoint /opt/docker/bin/
RUN chmod +x /opt/docker/bin/entrypoint

# now install the bot code
COPY . $CF_FEEDSTOCK_OPS_DIR
RUN conda activate base && \
    conda activate $CF_FEEDSTOCK_OPS_ENV && \
    cd $CF_FEEDSTOCK_OPS_DIR && \
    pip install --no-deps --no-build-isolation -e . && \
    cd - && \
    conda deactivate && \
    conda deactivate

# now make the conda user for running tasks and set the user
RUN useradd --shell /bin/bash -c "" -m conda
ENV HOME=/home/conda
ENV USER=conda
ENV LOGNAME=conda
ENV MAIL=/var/spool/mail/conda
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/conda/bin
# make symlink - actually directory gets made at run time in the entrypoint
RUN ln -s ${TMPDIR}/conda_user_conda_build_locks $HOME/.conda_build_locks
RUN chown conda:conda $HOME && \
    cp -R /etc/skel $HOME && \
    chown -R conda:conda $HOME/skel && \
    (ls -A1 $HOME/skel | xargs -I {} mv -n $HOME/skel/{} $HOME) && \
    rm -Rf $HOME/skel && \
    cd $HOME
USER conda

# deal with git config for user and mounted directory
RUN conda activate $CF_FEEDSTOCK_OPS_ENV && \
    git config --global --add safe.directory /cf_feedstock_ops_dir && \
    git config --global init.defaultBranch main && \
    git config --global user.email "conda@conda.conda" && \
    git config --global user.name "conda conda" && \
    conda deactivate && \
    conda init --all --user

# put the shell back
SHELL ["/bin/sh", "-c"]
