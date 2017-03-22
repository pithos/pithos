%define __debug_package 0

Summary: Pandora.com client for the GNOME desktop
Name: pithos
Version: 0.3.17
Release: 0
License: GPLv3
#Author: Kevin Mehall <km@kevinmehall.net>
Group: Applications/Multimedia
URL: http://kevinmehall.net/p/pithos/
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

Requires: pyxdg
Requires: pygtk2
Requires: pygobject2
Requires: PyXML
Requires: dbus-python
Requires: gstreamer-python
Requires: gstreamer-plugins-good
Requires: gstreamer-plugins-bad
BuildRequires: python-distutils-extra

%description
Pithos is a native Pandora Radio client for Linux. It's much more lightweight
than the Pandora.com web client, and integrates with desktop features such as media
keys, notifications, and the sound menu.

Pithos is not affiliated with or endorsed by Pandora Media, Inc.

%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
python setup.py install --root=$RPM_BUILD_ROOT --prefix=/usr
# Cleanup installed files that are better handled in %files
rm -rf $RPM_BUILD_ROOT/usr/share/doc

%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc README.md CHANGELOG
%{_bindir}/%{name}
%{python_sitelib}/*
%{_desktopdir}/*.desktop
%{_iconsscaldir}/*.svg
%{_datadir}/%{name}


%changelog
* Wed Dec 12 2012 Nathaniel Clark <Nathaniel.Clark@misrule.us> - 0.3.17
- Initial build.

