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
import CreatePlan from "../pages/CreatePlan";

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
        <Sider
          trigger={null}
          collapsible={false}
          collapsed={collapse}
          style={{ minHeight: "100vh", background: "#CCA43B" }}
        >
          <SideBar />
        </Sider>
        <Layout>
          <Header
            className="siteLayoutBackground"
            style={{ padding: 0, background: "#CCA43B" }}
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
              <Route path="/" element={<Dashboard />} />
              <Route path="/plans" element={<ViewPlans />} />
              <Route path="create-plan" element={<CreatePlan />} />
              <Route path="/customers" element={<ViewCustomers />} />
              <Route path="/customers-create" element={<CreatePlan />} />
              <Route path="/settings" element={<ViewSettings />} />
              <Route path="/redirectstripe" element={<StripeRedirect />} />
            </Routes>
          </Content>
          <Footer style={{ textAlign: "center" }}>Lotus Tech Co. @2022</Footer>
        </Layout>
      </Layout>
    </div>
  );
};

export default AppRoutes;
