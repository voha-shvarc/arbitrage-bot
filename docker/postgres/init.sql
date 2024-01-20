create database bot;
create role root;
alter role root with password 'example';
alter role root with login;
create database root;
grant all privileges on database root to root;