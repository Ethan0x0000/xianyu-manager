import { Card, Col, Divider, Row, Space, Tag, Typography, theme as antdTheme } from 'antd'

const GITHUB_URL = 'https://github.com/Ethan0x0000/xianyu-manager'

export default function AboutPage() {
  const { token } = antdTheme.useToken()

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: token.marginXS, marginTop: 0 }}>
          闲鱼管理系统
        </Typography.Title>
        <Space size="small" wrap>
          <Tag color="blue">v0.1.0</Tag>
          <Tag color="default">MIT License</Tag>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col span={24} xl={16}>
          <Card title="项目说明">
            <Typography.Paragraph>
              闲鱼管理系统是一个面向单管理员场景的开源运营后台，用于统一管理多闲鱼账号的商品、订单、自动回复、自动发货与运行日志。
            </Typography.Paragraph>
            <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
              当前前端版本聚焦于后台管理体验，保留清晰的信息结构与开源项目所需的基础说明，不包含任何个人收款、外部推广或与项目无关的展示内容。
            </Typography.Paragraph>
          </Card>
        </Col>

        <Col span={24} xl={8}>
          <Card title="开源信息">
            <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
              <div>
                <Typography.Text type="secondary">项目主页</Typography.Text>
                <br />
                <Typography.Link href={GITHUB_URL} rel="noreferrer" target="_blank">
                  GitHub 仓库
                </Typography.Link>
              </div>

              <div>
                <Typography.Text type="secondary">许可证</Typography.Text>
                <br />
                <Typography.Text>MIT License</Typography.Text>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card>
        <Typography.Title level={4}>项目边界</Typography.Title>
        <Divider style={{ marginBlock: token.marginSM }} />
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          本页面仅展示项目名称、版本、说明、代码仓库与许可证信息，便于在 OSS 场景下安全分发与维护。
        </Typography.Paragraph>
      </Card>
    </Space>
  )
}
