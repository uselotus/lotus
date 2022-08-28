import React, { FC } from "react";
import { Menu } from "antd";
import {
  UserOutlined,
  VideoCameraOutlined,
  UploadOutlined,
} from "@ant-design/icons";
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
      <Menu theme="dark" mode="vertical" selectedKeys={[location.pathname]}>
        <Menu.Item key="/dashboard" onClick={handleDashboardClick}>
          <UserOutlined />
          <span> Dashboard</span>
        </Menu.Item>
        <Menu.Item key="/customers" onClick={handleCustomersClick}>
          <VideoCameraOutlined />
          <span> Customers</span>
        </Menu.Item>
        <Menu.Item key="/plans" onClick={handlePlansClick}>
          <UploadOutlined />
          <span> Plans</span>
        </Menu.Item>
        <Menu.Item
          key="/settings"
          title="Settings"
          onClick={handleSettingsClick}
          className="absolute bottom-0"
        >
          <span> Settings</span>
        </Menu.Item>
      </Menu>
    </div>
  );
};

export default SideBar;
