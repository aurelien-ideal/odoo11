# The first argument needs to be the path to a cordova project directory
# The second argument is the platform, i.e. android, ios,...
echo "Creating 'www' bundle for cordova app in directory" $1

./generate_extension.sh

[ -d www ] || mkdir www
cp -r extension/static www
cp extension/timesheet.html www/index.html

cp -r www $1
cp www/static/src/img/icon.png $1

cd $1
cordova prepare $2
