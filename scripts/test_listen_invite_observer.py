"""CPU-only readiness/endpoint rejection tests; never touch the clipboard or launch a game."""
import copy
import unittest

from test_unreal_listen_invite import observed_sdl_video_driver,rendered_graphics,waiting_ready


def fixture():
    ids=['camp_'+str(i) for i in range(6)]
    scenes=[{'card_id':name,'capture_ready':True,'post_zero_captures':2,
        'compilation_zero_capture':2,'compilation_zero_frame':10,'captures':5,
        'last_ready_capture_frame':14,'condition_revision':0,'fire_sheets':0,
        'render_readiness':{'display_ready':True,'expected_meshes':2,'pending_psos':0,
            'missing_registrations':0,'missing_render_states':0,'dirty_render_states':0,'missing_proxies':0,
            'complete_submissions':2,'ordered_capture_fence_complete':True,
            'last_painted_placeholder':False,'last_painted_frame':15}} for name in ids]
    return {'snapshot':{'hosted':True,'connected':1,'seat':0,'view':{'status':'selection',
        'players':[{'offers':[{'id':name} for name in ids]},{}]}},
        'hud':{'hud_size':[1920,1080],'invite_buttons':[{'endpoint':'192.0.2.16:19679',
            'visible':True,'enabled':True,'min':[20,120],'max':[400,180]}],
            'portraits':{'compilation':{'telemetry_version':1,'available':True,'mode':'editor_compilers',
                'required_post_zero_captures':2,'shader_jobs':0,'asset_jobs':0,'shader_active':False,'ready':True,'frame':16},
                'scenes':scenes}}}


class InviteReadinessTests(unittest.TestCase):
    def test_clipboard_host_uses_real_x11_window(self):
        flags=rendered_graphics((1280,720))
        self.assertNotIn('-RenderOffscreen',flags)
        self.assertIn('-windowed',flags)
        self.assertIn('-sdlvideodriver=x11',flags)
        self.assertIn('-ResX=1280',flags)
        self.assertIn('-ResY=720',flags)

    def test_actual_driver_log_is_required_and_dummy_is_distinct(self):
        self.assertIsNone(observed_sdl_video_driver('Initializing SDL.'))
        self.assertEqual(observed_sdl_video_driver("LogInit: Using SDL video driver 'dummy'"),'dummy')
        self.assertEqual(observed_sdl_video_driver("LogInit: Using SDL video driver 'x11'"),'x11')
        self.assertEqual(observed_sdl_video_driver("Using SDL video driver 'x11'\nUsing SDL video driver 'dummy'"),'dummy')

    def test_final_six_portraits_and_custom_port_pass(self):
        self.assertTrue(waiting_ready(fixture(),19679))

    def test_cold_shaders_cannot_pass(self):
        state=fixture();state['hud']['portraits']['compilation']['shader_jobs']=24
        self.assertFalse(waiting_ready(state,19679))

    def test_final_render_not_yet_painted_cannot_pass(self):
        for field,value in [('last_painted_placeholder',True),('last_painted_frame',0),('pending_psos',1)]:
            state=fixture();state['hud']['portraits']['scenes'][2]['render_readiness'][field]=value
            with self.subTest(field=field):self.assertFalse(waiting_ready(state,19679))

    def test_all_six_camps_are_required(self):
        state=fixture();state['hud']['portraits']['scenes'].pop()
        self.assertFalse(waiting_ready(state,19679))

    def test_endpoint_port_must_equal_driver_port(self):
        self.assertFalse(waiting_ready(fixture(),7777))

    def test_wrong_or_unarranged_endpoints_fail(self):
        for field,value in [('endpoint','127.0.0.1:19679'),('endpoint','0.1.2.3:19679'),
            ('endpoint','255.255.255.255:19679'),('min',[]),('max',[3000,180]),('visible',False)]:
            state=fixture();state['hud']['invite_buttons'][0][field]=value
            with self.subTest(field=field,value=value):self.assertFalse(waiting_ready(state,19679))

    def test_duplicate_suggestions_fail(self):
        state=fixture();state['hud']['invite_buttons'].append(copy.deepcopy(state['hud']['invite_buttons'][0]))
        self.assertFalse(waiting_ready(state,19679))

    def test_joined_state_is_not_waiting_evidence(self):
        state=fixture();state['snapshot']['connected']=2
        self.assertFalse(waiting_ready(state,19679))


if __name__=='__main__':unittest.main(verbosity=2)
