NGENCERF_APP=/ngencerf-app

# Prompt for gitlab token
echo Paste your gitlab token
gedit $NGENCERF_APP/.gitlab_token

git config --global url."https://oauth2:$(cat /ngencerf-app/.gitlab_token)@gitlab.sh.nextgenwaterprediction.com/".insteadOf "https://gitlab.sh.nextgenwaterprediction.com/"

cd $NGENCERF_APP

echo Cloning repos
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf_ui.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf-server.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngencerf-docker.git
echo
git clone -b development --recurse-submodules https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-cal.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-forcing.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-fcst.git
echo
git clone -b development https://gitlab.sh.nextgenwaterprediction.com/NGWPC/nwm-ngen/ngen-pw-automation
echo


echo Logging into Docker.  Enter your AWS credentials if prompted
docker login registry.sh.nextgenwaterprediction.com

echo
echo Pulling docker images

echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-cal:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-forcing/ngen-bmi-forcing:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-forcing/ngen-lumped-forcing:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-fcst:latest
echo
docker pull registry.sh.nextgenwaterprediction.com/ngwpc/nwm-ngen/ngen-verf:latest

echo
echo Building singularities
set -x
$NGENCERF_APP/ngen-pw-automation/build_singularity.sh --release-type=development all

echo
echo Building nginx singularity

cd $NGENCERF_APP
git clone https://github.com/parallelworks/interactive_session.git
cp interactive_session/downloads/jupyter/nginx-unprivileged.sif singularity
rm -rf interactive_session

echo
cd ngencerf-server
cp ngencerf-services.env ngencerf-services.override.env
echo

echo Editing ngencerf-server.override.env
echo Update database host, password and EDS url
gedit ngencerf-server.override.env
echo

echo Editing .env
echo Update ngen-cal and ngen-forcing tags
gedit .env
echo

echo Preparing static data
sudo mkdir -p /ngencerf-app/data/ngen-cal-data/ngen-static-files
sudo chown -R `whoami`:pwuser /ngencerf-app/data/ngen-cal-data
sudo chmod -R g+rwx /ngencerf-app/data/ngen-cal-data

echo

echo Copying module_parameter_files directory from the ngen-cal repo
cp --archive /ngencerf-app/ngen-cal/module_parameter_files /ngencerf-app/data/ngen-cal-data/ngen-static-files/

echo

echo Paste export statements for your AWS credentials
gedit /tmp/aws.credentials

source /tmp/aws.credentials
echo Copying data from NGWPC data bucket
aws s3 sync s3://ngwpc-dev/ngen-static-files /ngencerf-app/data/ngen-cal-data/ngen-static-files/.

