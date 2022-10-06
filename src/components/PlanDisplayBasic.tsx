import React, { FC } from 'react'
import { PlanType } from '../types/plan-type'
import {
  Card,
  Menu,
  Dropdown,
  List,
  Statistic,
  Descriptions,
  Button,
  Col,
  Row,
  Space,
  Typography,
} from 'antd'
import { Plan } from '../api/api'
import { ArrowDownOutlined, MoreOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { Components } from 'antd/lib/date-picker/generatePicker'
import { Paper } from './base/Paper'
import { Title } from './base/Typograpy/index.'

function PlanDisplayBasic(props: {
  plan: PlanType
  deletePlan: (billing_plan_id: string) => void
}) {
  const planMenu = (
    <Menu>
      <Menu.Item key='0'>
        <Link to='/update-plan' state={{ plan: props.plan }}>
          Edit
        </Link>
      </Menu.Item>
      <Menu.Item key='1' disabled={props.plan.active_subscriptions !== 0}>
        <a href='#' onClick={() => props.deletePlan(props.plan.billing_plan_id)}>
          Delete
        </a>
      </Menu.Item>
    </Menu>
  )

  const componentMenu = (
    <Menu>
      {props.plan.components.map((component) => (
        <Menu.Item key={component.id} className='border-2 bg-white'>
          {component.billable_metric.billable_metric_name} ${component.cost_per_batch} per{' '}
          {component.metric_units_per_batch}
        </Menu.Item>
      ))}
    </Menu>
  )

  const featureMenue = (
    <Menu>
      {props.plan.features.map((feature) => (
        <Menu.Item key={feature.feature_name}>{feature.feature_name}</Menu.Item>
      ))}
    </Menu>
  )

  return (
    <Paper>
      <Descriptions
        title={props.plan.name}
        contentStyle={{
          fontSize: 32,
        }}
        className='text-4xl'
        extra={
          <Dropdown overlay={planMenu} trigger={['click']}>
            <Button type='text' onClick={(e) => e.preventDefault()}>
              <MoreOutlined />
            </Button>
          </Dropdown>
        }
      />
      <p className=''>{props.plan.description}</p>
      <Row>
        <Col span={12}>
          <Descriptions size='small' column={2}>
            <Descriptions.Item label='Plan ID' span={2}>
              {props.plan.billing_plan_id}
            </Descriptions.Item>
            <Descriptions.Item label='Interval'>{props.plan.interval}</Descriptions.Item>
            <Descriptions.Item label='Recurring Price'>
              {/* // use curreny formatter */}${props.plan.flat_rate}
            </Descriptions.Item>
            <Descriptions.Item label='Date Created'>{props.plan.time_created}</Descriptions.Item>
            <Descriptions.Item label='Pay In Advance'>Yes</Descriptions.Item>
          </Descriptions>
        </Col>

        <Col span={8}>
          <Space>
            <Dropdown overlay={componentMenu}>
              <Button>
                Components: {props.plan.components.length} <ArrowDownOutlined />
              </Button>
            </Dropdown>
            <Dropdown overlay={featureMenue}>
              <Button className='bg-[#CCA43B69]'>
                Features: {props.plan.components.length} <ArrowDownOutlined />
              </Button>
            </Dropdown>
          </Space>
        </Col>

        <Col span={4}>
          <div className='justify-self-center self-center text-center'>
            <h1 className='font-main font-bold text-4xl'>{props.plan.active_subscriptions}</h1>
            <h3>Active Subscriptions</h3>
          </div>
        </Col>
      </Row>
    </Paper>
  )
}

export default PlanDisplayBasic
