
sudo chown "${USER}:pwuser" -R /ngencerf-app/nwm-automation-scripts
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngen
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngen-cal
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngen-forcing
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngen-fcst
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngen-verf
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngencerf-server
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngencerf-docker
sudo chown "${USER}:pwuser" -R /ngencerf-app/ngencerf_ui
sudo chown "${USER}:pwuser" -R /ngencerf-app/singularity
sudo chown "${USER}:pwuser" -R /ngencerf-app/.gitlab_token

git config --global url."https://oauth2:$(cat /ngencerf-app/.gitlab_token)@gitlab.sh.nextgenwaterprediction.com/".insteadOf " https://gitlab.sh.nextgenwaterprediction.com/"

git config --global --add safe.directory /ngencerf-app/nwm-automation-scripts
git config --global --add safe.directory /ngencerf-app/ngen
git config --global --add safe.directory /ngencerf-app/ngen-cal
git config --global --add safe.directory /ngencerf-app/ngen-forcing
git config --global --add safe.directory /ngencerf-app/ngen-fcst
git config --global --add safe.directory /ngencerf-app/ngen-verf
git config --global --add safe.directory /ngencerf-app/ngencerf-server
git config --global --add safe.directory /ngencerf-app/ngencerf-docker
git config --global --add safe.directory /ngencerf-app/ngencerf_ui
