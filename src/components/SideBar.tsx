import React, { FC } from "react";
import { Divider, Menu } from "antd";
import {
  BarChartOutlined,
  UserOutlined,
  UploadOutlined,
  SettingOutlined,
  BookOutlined,
  BorderlessTableOutlined,
  LogoutOutlined,
} from "@ant-design/icons";

import { useNavigate, useLocation } from "react-router";
import logo from "../assets/images/corner_logo.svg";
import "./SideBar.css";
import { Authentication } from "../api/api";

const SideBar: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleCustomersClick = () => {
    navigate("/customers");
  };
  const handlePlansClick = () => {
    navigate("/plans");
  };
  const handleDashboardClick = () => {
    navigate("/dashboard");
  };
  const handleSettingsClick = () => {
    navigate("/settings");
  };

  const handleSubscriptionsClick = () => {
    navigate("/subscriptions");
  };

  const handleMetricsClick = () => {
    navigate("/metrics");
  };

  const handleLogoutClick = () => {
    Authentication.logout().then(() => {
      window.location.reload();
      navigate("/");
    });
  };

  return (
    <div>
      <Menu
        mode="vertical"
        selectedKeys={[location.pathname]}
        className="min-h-screen"
      >
        <div
          style={{
            height: "100%",
            margin: "30px",
            background: "#000000",
          }}
        >
          <img src={logo} alt="lotus" />
        </div>
        <Menu.Item key="/dashboard" onClick={handleDashboardClick}>
          <BarChartOutlined />
          <span> Dashboard</span>
        </Menu.Item>
        <Menu.Item key="/customers" onClick={handleCustomersClick}>
          <UserOutlined />
          <span> Customers</span>
        </Menu.Item>
        <Menu.Item key="/plans" onClick={handlePlansClick}>
          <UploadOutlined />
          <span> Plans</span>
        </Menu.Item>
        <Menu.Item key="/metrics" onClick={handleMetricsClick}>
          <BorderlessTableOutlined />
          <span> Metrics</span>
        </Menu.Item>
        {/* <Menu.Item key="/subscriptions" onClick={handleSubscriptionsClick}>
          <BookOutlined />
          <span> Subscriptions</span>
        </Menu.Item> */}
        <Divider />
        <Menu.Item key="/docs">
          <BookOutlined />
          <span>
            {" "}
            <a
              target="_blank"
              rel="noreferrer"
              href="https://docs.uselotus.io/docs/intro"
            >
              Docs
            </a>
          </span>
        </Menu.Item>
        <Menu.Item
          key="/settings"
          onClick={handleSettingsClick}
          className="flex flex-row"
        >
          <SettingOutlined />
          <span> Settings</span>
        </Menu.Item>
        <Menu.Item key="logout" onClick={handleLogoutClick}>
          <LogoutOutlined />
          <span> Logout</span>
        </Menu.Item>
      </Menu>
    </div>
  );
};

export default SideBar;
