import React, { FC, useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "../components/Dashboard";
import ViewPlans from "../pages/ViewPlans";
import ViewCustomers from "../pages/ViewCustomers";
import ViewSettings from "../pages/ViewSettings";
import StripeRedirect from "../pages/StripeRedirect";

// import MainContent from "./components/MainContent";
import SideBar from "../components/SideBar";
import { Layout } from "antd";
import { MenuUnfoldOutlined, MenuFoldOutlined } from "@ant-design/icons";

const { Header, Sider, Content, Footer } = Layout;

const AppRoutes: FC = () => {
  const [collapse, setCollapse] = useState(false);

  const handleToggle = (event: any) => {
    event.preventDefault();
    collapse ? setCollapse(false) : setCollapse(true);
  };

  useEffect(() => {
    window.innerWidth <= 760 ? setCollapse(true) : setCollapse(false);
  }, []);
  return (
    <div>
      <Layout>
        <Sider trigger={null} collapsible collapsed={collapse}>
          <SideBar />
        </Sider>
        <Layout>
          <Header
            className="siteLayoutBackground"
            style={{ padding: 0, background: "#001529" }}
          >
            {React.createElement(
              collapse ? MenuUnfoldOutlined : MenuFoldOutlined,
              {
                className: "trigger",
                onClick: handleToggle,
                style: { color: "#fff" },
              }
            )}
          </Header>
          <Content
            style={{
              margin: "24px 16px",
              padding: 24,
              minHeight: "calc(100vh - 114px)",
              background: "#fff",
            }}
          >
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/plans" element={<ViewPlans />} />
              <Route path="/customers" element={<ViewCustomers />} />
              <Route path="/settings" element={<ViewSettings />} />
              <Route
                path="/redirectstripe/:code/:error"
                element={<StripeRedirect />}
              />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Content>
          <Footer style={{ textAlign: "center" }}>Lotus @2022</Footer>
        </Layout>
      </Layout>
    </div>
  );
};

export default AppRoutes;
