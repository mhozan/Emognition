aa=load('clown');
jimg = im2java(aa.X);
figure
frame = javax.swing.JFrame;
frame.setUndecorated(true);
icon = javax.swing.ImageIcon(jimg);
label = javax.swing.JLabel(icon);
frame.getContentPane.add(label);
frame.pack;
screenSize = get(0,'ScreenSize');  %# Get the screen size from the root object
frame.setSize(screenSize(3),screenSize(4));
frame.setLocation(0,0);
frame.show;

% frame.hide;