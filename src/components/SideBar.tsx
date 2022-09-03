import React, { FC } from "react";
import { Divider, Menu } from "antd";
import {
  BarChartOutlined,
  UserOutlined,
  UploadOutlined,
  SettingOutlined,
  BookOutlined,
} from "@ant-design/icons";
import { GearIcon, ImageIcon, SunIcon } from "@radix-ui/react-icons";

import { useNavigate, useLocation } from "react-router";
import logo from "../assets/images/corner_logo.svg";
import "./SideBar.css";

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

  return (
    <div>
      <div
        style={{
          height: "32px",
          background: "#fff",
          margin: "16px",
        }}
      >
        <img src={logo} alt="lotus" />
      </div>
      <Menu
        mode="vertical"
        selectedKeys={[location.pathname]}
        className="min-h-screen"
      >
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
        <Menu.Item key="/subscriptions" onClick={handleSubscriptionsClick}>
          <BookOutlined />
          <span> Subscriptions</span>
        </Menu.Item>
        <Divider />
        <Menu.Item
          key="/settings"
          onClick={handleSettingsClick}
          className="flex flex-row"
        >
          <SettingOutlined />
          <span> Settings</span>
        </Menu.Item>
      </Menu>
    </div>
  );
};

export default SideBar;
