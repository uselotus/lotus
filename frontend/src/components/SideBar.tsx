import React, { FC } from "react";
import { Menu } from "antd";
import {
  UserOutlined,
  DashboardOutlined,
  SettingOutlined,
  DatabaseOutlined,
  BookOutlined,
  BorderlessTableOutlined,
  LineChartOutlined,
  LogoutOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";

import { useNavigate, useLocation } from "react-router-dom";
import { Authentication, instance } from "../api/api";
import { ItemType } from "antd/lib/menu/hooks/useItems";

const imgUrl = new URL("./Head.png", import.meta.url).href;

const SideBar: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogoutClick = () => {
    //call the logout request and navigate to the root, reagrdless of success or failure
    Authentication.logout().finally(() => {
      //remove the lotusAccessToken from session storage
      sessionStorage.removeItem("lotusAccessToken");
      //remove the Bearer header from the axios instance
      delete instance.defaults.headers.common["Authorization"];
      window.location.href = "https://www.uselotus.io/";
      // window.location.reload();
      // navigate("/");
    });
  };

  const menuItemsBasic: ItemType[] = [
    {
      key: "/dashboard",
      icon: <DashboardOutlined />,
      label: "Dashboard",
      onClick: () => navigate("/dashboard"),
    },
    {
      key: "/experiments",
      icon: <ExperimentOutlined />,
      label: "Experiments",
      onClick: () => navigate("/experiments"),
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
      key: "/add-ons",
      icon: <DatabaseOutlined />,
      label: "Add-ons",
      onClick: () => navigate("/add-ons"),
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
        window.open(
          "https://docs.uselotus.io/docs/overview/why-lotus",
          "_blank"
        ),
    },
  ];

  const menuItemsAdmin: ItemType[] = [
    {
      key: "/dashboard",
      icon: <DashboardOutlined />,
      label: "Dashboard",
      onClick: () => navigate("/dashboard"),
    },
    {
      key: "/experiments",
      icon: <ExperimentOutlined />,
      label: "Experiments",
      onClick: () => navigate("/experiments"),
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
      key: "/add-ons",
      icon: <DatabaseOutlined />,
      label: "Add-ons",
      onClick: () => navigate("/add-ons"),
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
        window.open(
          "https://docs.uselotus.io/docs/overview/why-lotus",
          "_blank"
        ),
    },
    {
      key: "/settings",
      icon: <SettingOutlined />,
      label: "Settings",
      onClick: () => navigate("/settings/general"),
    },
  ];

  const menuItems =
    (import.meta as any).env.VITE_IS_DEMO === "true"
      ? menuItemsBasic
      : menuItemsAdmin;

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
          style={{ background: "#fafafa" }}
        />
      </div>

      <div className="mb-5">
        <Menu
          style={{ background: "#fafafa" }}
          items={[
            {
              type: "divider",
            },
            {
              key: "/logout",
              icon: <LogoutOutlined />,
              label: "Logout",
              onClick: handleLogoutClick,
            },
          ]}
        />
      </div>
    </div>
  );
};

export default SideBar;
