import React, { FC } from "react";
import { Menu, Progress } from "antd";
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
import { ItemType } from "antd/lib/menu/hooks/useItems";
import { Authentication } from "../api/api";
import useGlobalStore, { GlobalStoreState } from "../stores/useGlobalstore";
import { selectQuickStartProgress } from "../helpers/quickStartCheck";

const CustomQuickStartMenuItem = ({
  progressPercent = 0,
}: {
  progressPercent: number;
}) => (
  <div className="flex justify-start items-center">
    <BookOutlined />
    <span className="ml-1 mr-4">Quick Start</span>
    <Progress
      percent={progressPercent}
      strokeColor="#BF9F79"
      trailColor="#d7d5d5"
      showInfo={false}
      size="small"
    />
  </div>
);

const imgUrl = new URL("./Head.png", import.meta.url).href;

const SideBar: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const totalProgress = useGlobalStore(selectQuickStartProgress);

  const handleLogoutClick = () => {
    Authentication.logout().then(() => {
      window.location.reload();
      navigate("/");
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
    import.meta.env.VITE_IS_DEMO === "true" ? menuItemsBasic : menuItemsAdmin;

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
              key: "/quickstart",
              icon: (
                <CustomQuickStartMenuItem progressPercent={totalProgress} />
              ),
              onClick: () => navigate("/quickstart"),
            },
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
