import React, { FC } from "react";
import { Affix, Divider, Menu, MenuItemProps } from "antd";
import {
  BarChartOutlined,
  UserOutlined,
  DashboardOutlined,
  SettingOutlined,
  BookOutlined,
  BorderlessTableOutlined,
  LineChartOutlined,
  LogoutOutlined,
} from "@ant-design/icons";

import { useNavigate, useLocation } from "react-router";
import "./SideBar.css";
import { Authentication } from "../api/api";
import { Link } from "react-router-dom";

const imgUrl = new URL("./Head.png", import.meta.url).href;

const SideBar: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogoutClick = () => {
    Authentication.logout().then(() => {
      window.location.reload();
      navigate("/");
    });
  };
  console.log(location.pathname);

  const menuItems: any = [
    {
      key: "/dashboard",
      icon: <DashboardOutlined />,
      label: "Dashboard",
      onClick: () => navigate("/dashboard"),
    },
    {
      key: "/customers",
      icon: <UserOutlined />,
      label: "Customers",
      onClick: () => navigate("/customers"),
    },
    {
      key: "/plans",
      icon: <BorderlessTableOutlined />,
      label: "Plans",
      onClick: () => navigate("/plans"),
    },

    {
      key: "/metrics",
      icon: <LineChartOutlined />,

      label: "Metrics",
      onClick: () => navigate("/metrics"),
    },
    {
      type: "divider",
    },
    {
      label: "Docs",
      key: "/docs",
      icon: <BookOutlined />,
      onClick: () =>
        window.open("https://docs.uselotus.io/docs/intro", "_blank"),
    },
    {
      key: "/settings",
      icon: <SettingOutlined />,
      label: "Settings",
      onClick: () => navigate("/settings"),
    },
  ];

  return (
    <div
      className="h-screen flex flex-col justify-between"
      style={{
        position: "fixed",
        zIndex: 1,
        width: "200px",
        borderRight: "1px solid #e8e8e8",
      }}
    >
      <div>
        <img src={imgUrl} alt="lotus" className="mb-4" />
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
        />
      </div>

      <div className="mb-4">
        <Divider className="self-end" />
        <Menu>
          <Menu.Item
            key="logout"
            onClick={handleLogoutClick}
            icon={<LogoutOutlined />}
          >
            Logout
          </Menu.Item>
        </Menu>
      </div>
    </div>
  );
};

export default SideBar;
